# corpus/importer.py
# embedder.py
from __future__ import annotations
import json, time, re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core.resources import get_storage, get_db, get_provider
from adapters.db.neo4j import Neo4jAdapter
from adapters.llm.base import Provider  # votre Protocol

DEFAULT_BATCH = 128

# Batching configurable (batch_size).
# Index par série (évite le bruit inter-corpus et simplifie l’isolation).
# Dimension auto-déduite sur le premier batch et appliquée à l’index.
# Métadonnées stockées : series, file, page, order, provider, model, dims, ingest_ts.

@dataclass
class Embedder:
    provider: Optional[Provider] = None
    db: Optional[Neo4jAdapter] = None
    batch_size: int = DEFAULT_BATCH
    label: str = "Chunk"
    prop: str = "embedding"
    index_base: str = "chunkIndex"
    index_per_series: bool = True

    def __init__(self) -> None:
        self.storage = get_storage()
        self.provider = get_provider()
        self.db = get_db()

    # def __post_init__(self) -> None:
    #     self.db = self.db or Neo4jAdapter()

    def _index_name(self, series: str) -> str:
        return f"chunkIndex__{series}"
        # return f"{self.index_base}__{series}" if self.index_per_series else self.index_base

    def _safe_index_name(self, base: str) -> str:
        # 1) remplacer tout sauf [A-Za-z0-9_] par _
        name = re.sub(r'[^A-Za-z0-9_]', '_', base)
        # 2) si le 1er char n'est pas une lettre, préfixer
        if not re.match(r'^[A-Za-z]', name):
            name = f'idx_{name}'
        return name

    # ----------- ingestion corpus -----------
    def embed_corpus(self, series: str, *, dimensions: Optional[int] = None) -> Dict[str, Any]:
        """
        Ingestion des fichiers chunks d'une série:
        - lit data/series/<series>/chunks/_report.json
        - vectorise en batch
        - crée l'index vectoriel si besoin
        - upsert dans Neo4j
        """
        # storage = get_storage()
        series_dir = self.storage.ensure_series(series)
        chunks_dir = series_dir / "chunks"
        report_path = chunks_dir / "_report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Chunks report not found: {report_path}")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        items = report.get("items", [])

        index = None
        vec_dim: Optional[int] = None
        total_vectors = 0
        total_nodes = 0
        rows_batch: List[Dict[str, Any]] = []

        def flush():
            """Écrit les blocs de texte dans un fichier JSONL."""
            nonlocal total_nodes
            if not rows_batch:
                return
            total_nodes += self.db.upsert_chunks(rows=rows_batch, series=series, approach="embedder")
            # total_nodes += self.db.upsert_chunks(rows=rows_batch, label=self.label, prop=self.prop)     #(rows=rows_batch, label=self.label, prop=self.prop)
            rows_batch.clear()

        # Parcours des outputs *.chunks.jsonl
        for item in items:
            out_rel = item.get("output")
            if not out_rel:
                continue
            fpath = series_dir / out_rel
            if not fpath.exists():
                continue

            texts: List[str] = []
            metas: List[Dict[str, Any]] = []
            with fpath.open(encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    text = data.get("text", "")
                    doc = data.get("doc", {}) or {}
                    meta = data.get("meta", {}) or {}
                    filename = doc.get("filename") or Path(out_rel).stem
                    idx = data.get("idx", data.get("order", line_idx))
                    page = meta.get("page", data.get("page"))
                    cid = f"{series}:{filename}:{idx}"
                    texts.append(text)
                    metas.append({
                        "cid": cid,
                        "text": text,
                        "series": series,
                        "file": filename,
                        "page": page,
                        "order": idx,
                    })

            # Embedding en batch
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                # vecs = self.provider.embed_batch(batch_texts, dimensions=dimensions)
                vecs = self.embed_texts(batch_texts, dim=dimensions)
                if vecs:
                    if vec_dim is None:
                        vec_dim = len(vecs[0])
                        index = self._index_name(series)
                        index = self._safe_index_name(index)
                        if not self.db.check_index_exists(index):
                            self.db.create_vector_index(index, label=self.label, prop=self.prop,
                                                        dimensions=vec_dim, similarity="cosine")
                    total_vectors += len(vecs)
                    now = time.time()
                    for j, v in enumerate(vecs):
                        m = metas[i + j]
                        rows_batch.append({
                            "cid": m["cid"],
                            "text": m["text"],
                            "vec": v,
                            "series": m["series"],
                            "file": m["file"],
                            "page": m["page"],
                            "order": m["order"],
                            "provider": type(self.provider).__name__,
                            "model": getattr(self.provider, "embed_model", getattr(self.provider, "embed_dep", None)),
                            "dims": vec_dim,
                            "ts": now,
                        })
                    if len(rows_batch) >= 2000:
                        flush()

        flush()
        return {
            "series": series,
            "index": index,
            "dimensions": vec_dim,
            "vectors": total_vectors,
            "upserted_nodes": total_nodes,
        }
    
    
    def _hash_vec(self, text: str, dim: Optional[int] = 384) -> List[float]:
        import hashlib, math
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vals = []
        while len(vals) < (dim or 384):
            for b in h:
                vals.append((b - 128) / 128.0)
                if len(vals) >= (dim or 384):
                    break
        n = math.sqrt(sum(x*x for x in vals))
        return [x/(n or 1.0) for x in vals]

    def embed_texts(self, texts: Iterable[str], dim: Optional[int] = 384) -> List[List[float]]:
        if self.provider.embed_texts is not None:
            return self.provider.embed_texts(list(texts), dimensions=dim)
        return [self._hash_vec(t or "", dim=dim) for t in texts]

    # ----------- recherche top-k -----------
    def search(self, series: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Recherche les chunks les plus similaires à une requête donnée."""
        index = self._index_name(series)
        vec = self.provider.embed(query)
        return self.db.query_top_k(index, vec, k=k, series=series)