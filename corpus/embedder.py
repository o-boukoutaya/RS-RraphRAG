# corpus/importer.py
# embedder.py
from __future__ import annotations
import json, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core.resources import get_storage
from adapters.db.neo4j import Neo4jAdapter
from adapters.llm.base import Provider  # votre Protocol

DEFAULT_BATCH = 128

# Batching configurable (batch_size).
# Index par série (évite le bruit inter-corpus et simplifie l’isolation).
# Dimension auto-déduite sur le premier batch et appliquée à l’index.
# Métadonnées stockées : series, file, page, order, provider, model, dims, ingest_ts.

@dataclass
class Embedder:
    provider: Provider
    db: Optional[Neo4jAdapter] = None
    batch_size: int = DEFAULT_BATCH
    label: str = "Chunk"
    prop: str = "embedding"
    index_base: str = "chunkIndex"
    index_per_series: bool = True

    def __post_init__(self) -> None:
        self.db = self.db or Neo4jAdapter()

    def _index_name(self, series: str) -> str:
        return f"{self.index_base}__{series}" if self.index_per_series else self.index_base

    # ----------- ingestion corpus -----------
    def embed_corpus(self, series: str, *, dimensions: Optional[int] = None) -> Dict[str, Any]:
        """
        Ingestion des fichiers chunks d'une série:
        - lit data/series/<series>/chunks/_report.json
        - vectorise en batch
        - crée l'index vectoriel si besoin
        - upsert dans Neo4j
        """
        storage = get_storage()
        series_dir = storage.ensure_series(series)
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
            total_nodes += self.db.upsert_chunks(rows=rows_batch, label=self.label, prop=self.prop)     #(rows=rows_batch, label=self.label, prop=self.prop)
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
                vecs = self.provider.embed_batch(batch_texts, dimensions=dimensions)
                vecs = self.embed_texts(batch_texts, dim=dimensions)
                if vecs:
                    if vec_dim is None:
                        vec_dim = len(vecs[0])
                        index = self._index_name(series)
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
                            "model": getattr(self.provider, "embed_model",
                                    getattr(self.provider, "embed_dep", None)),
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












# from datetime import datetime
# from importlib.resources import files
# from typing import Any, Dict, Iterable, List, Set, Optional
# from fastapi import UploadFile
# from corpus.models import ImportReport, RejectedFile, Document
# from app.core.config import get_settings
# from app.core.resources import get_provider, get_storage
# # from corpus.storage import LocalStorage
# # from adapters.storage.local import LocalStorage
# from app.core.resources import get_db
# from adapters.storage.base import ExtensionNotAllowed, EmptyFile, FileTooLarge  # types d'erreurs
# from .utils import sanitize_series, make_series_id
# from pathlib import Path
# # from functools import lru_cache


# class Embedders:
#     """Service métier : gère l'import multi-fichiers et les règles d'acceptation."""

#     def __init__(self) -> None:
#         # self.storage = LocalStorage()
#         self.db = get_db()
#         self.provider = get_provider()
#         self.data = get_storage()
    
#     def run(self, chunks: List[Dict], *, version: str | None = None):
#         """Ingère une liste de dictionnaires : {"text": …}."""
#         texts = [c["text"] for c in chunks]
#         embeddings = self.provider.embed_texts(texts)
#         # if not self.db.check_index_exists():
#             # dim = len(embeddings[0])
#             # self.db.create_index(dim=dim)
#         # self.db.save(texts=texts, embeddings=embeddings, version=version)
#         return len(embeddings)
    
#     # Dans Adapter>db>neo4j cette fonction doit être existe
#     # def check_index_exists(self) -> bool:
#     #     q = "SHOW INDEXES YIELD name WHERE name = $name RETURN count(*) AS c"
#     #     with self.driver.session(database=self.db) as s:
#     #         return s.run(q, name=self._sanitize(self.index_name)).single()["c"] > 0

#     # Dans Adapter>db>neo4j cette fonction doit être existe
#     # def create_index(self, dim: int = 768, similarity: str = "cosine"):
#     #     """Crée un vector index (Neo4j 5) en neutralisant les caractères invalides.
#     #     Exemple de requête générée :
#     #     CREATE VECTOR INDEX `index_110625_022017` IF NOT EXISTS
#     #     FOR (c:Chunk) ON (c.embedding)
#     #     OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }
#     #     """
#     #     safe_name = self._sanitize(self.index_name)
#     #     q = (
#     #         f"CREATE VECTOR INDEX `{safe_name}` IF NOT EXISTS "
#     #         f"FOR (c:{self.node_label}) ON (c.{self.embed_prop}) "
#     #         f"OPTIONS {{ indexConfig: {{ `vector.dimensions`: {dim}, "
#     #         f"`vector.similarity_function`: '{similarity}' }} }}"
#     #     )
#     #     with self.driver.session(database=self.db) as s:
#     #         s.run(q)

#     # embedding pipeline/activity
#     def run_from_series(self, texts: List[str], series_version: str, *, similarity: str = "cosine") -> int:
#         """
#         Ingeste une série (extraction(existe) → chunks(existe) → embeddings(this part) → Neo4j).

#         Parameters
#         ----------
#         series_version : str
#             Identifiant de la série (ex. "110625-022017").
#         version : str, optional
#             Tag stocké dans le nœud ; défaut = series_version.
#         similarity : str, optional
#             Fonction de similarité de l’index vectoriel
#             ("cosine", "euclidean", "dotproduct").
#         Returns
#         -------
#         int
#             Nombre de chunks réellement indexés.
#         """

#         # 1. Préparer les données ------------------------------------------------
#         embeddings: List[List[float]] = self.provider.embed_texts(texts)
#         dim: int = len(embeddings[0])
        
#         # 2. Créer l’index vectoriel (une seule fois) ----------------------------
#         if not self.db.check_index_exists():
#             self.db.create_index(dim=dim, similarity=similarity)
        
#         # 3. Transformer en lignes batch ----------------------------------------
#         stamp = datetime.now().isoformat(timespec="seconds")
#         rows: List[Dict[str, Any]] = [
#             {
#                 "cid": f"{series_version}-{i:06d}",
#                 "text": txt,
#                 "vec":  vec,
#                 "series": series_version,
#                 "ingest_ts": stamp,
#             }
#             for i, (txt, vec) in enumerate(zip(texts, embeddings), 1)
#         ]

#         # 4. Insérer / mettre à jour les nœuds Chunk + vecteur -------------------
#         cypher_chunks = """
#             UNWIND $rows AS row
#             MERGE (c:Chunk {id: row.cid})
#             ON CREATE SET
#                     c.text        = row.text,   
#                     c.embedding   = row.vec,
#                     c.series      = row.series,
#                     c.ingest_ts   = row.ingest_ts
#             ON MATCH SET
#                     c.text        = row.text,
#                     c.embedding   = row.vec,
#                     c.series      = row.series
#             """
#         # _driver déclaré sous db : c'est GraphDatabase (from neo4j import GraphDatabase)
#         # existe une fonction session dans neo4j.py mais ne retourne rien et termine par finally:s.close()
#         with self.db._driver.session(database="db_name") as s:
#             s.run(cypher_chunks, rows=rows)
            
#             # 5. Relations NEXT_CHUNK (séquencement) ---------------------------
#             rels = [
#                 {"from": rows[i]["cid"], "to": rows[i + 1]["cid"]}
#                 for i in range(len(rows) - 1)
#             ]
#             if rels:
#                 cypher_rels = """
#                 UNWIND $rels AS rel
#                 MATCH (c1:Chunk {id: rel.from})
#                 MATCH (c2:Chunk {id: rel.to})
#                 MERGE (c1)-[:NEXT_CHUNK]->(c2)
#                 """
#                 s.run(cypher_rels, rels=rels)

#         return len(rows)