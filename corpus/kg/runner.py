# corpus/kg/runner.py
from __future__ import annotations
import json, pathlib, time, hashlib,uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from app.core.config import get_settings
from app.core.resources import get_storage
from adapters.llm.base import Provider
from adapters.db.neo4j import Neo4jAdapter
from corpus.kg.extract import extract_from_text

def _hash_text(t: str) -> str:
    return hashlib.sha1((t or "").encode("utf-8")).hexdigest()

@dataclass
class KGRunner:
    provider: Provider
    db: Optional[Neo4jAdapter] = None
    domain_hint: str = "immobilier"
    batch_upsert: int = 1000

    def __post_init__(self):
        self.db = self.db or Neo4jAdapter()

    def run_series(self, series: str, *, limit_chunks: Optional[int] = None) -> Dict[str, Any]:
        cfg = get_settings()
        storage = get_storage()
        sdir = storage.ensure_series(series)
        chunks_dir = sdir / "chunks"
        report_path = chunks_dir / "_report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Chunks report not found: {report_path}")

        out_dir = sdir / "kg"
        out_dir.mkdir(parents=True, exist_ok=True)

        log_path = out_dir / "_cypher.log.jsonl"
        self.db.enable_query_logging(log_path)

        
        build_id = f"build-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        approach = "A1" # req.approach or "A1"  # par ex.

        report = json.loads(report_path.read_text(encoding="utf-8"))
        items = report.get("items", [])
        started = time.time()

        self.db.ensure_base_schema()

        ents_batch: List[Dict[str, Any]] = []
        rels_batch: List[Dict[str, Any]] = []
        links_batch: List[Dict[str, Any]] = []

        total_chunks = 0
        total_entities = 0
        total_relations = 0
        dedup_entities: Set[str] = set()
        dedup_relations: Set[tuple] = set()

        for it in items:
            out_rel = it.get("output")
            if not out_rel:
                continue
            fpath = sdir / out_rel
            if not fpath.exists():
                continue

            kg_jsonl = out_dir / f"{pathlib.Path(it['filename']).stem}.kg.jsonl"
            done_hashes: Set[str] = set()
            if kg_jsonl.exists():
                for line in kg_jsonl.read_text(encoding="utf-8").splitlines():
                    try:
                        obj = json.loads(line)
                        if "hash" in obj:
                            done_hashes.add(obj["hash"])
                    except Exception:
                        pass

            with fpath.open(encoding="utf-8") as f:
                for line in f:
                    if limit_chunks and total_chunks >= limit_chunks:
                        break
                    data = json.loads(line)
                    text = data.get("text", "")
                    if not text.strip():
                        continue
                    filename = (data.get("doc") or {}).get("filename") or pathlib.Path(out_rel).stem
                    idx = data.get("idx", data.get("order", 0))
                    page = data.get("page")
                    chunk_id = f"{series}:{filename}:{idx}"
                    h = _hash_text(text)
                    if h in done_hashes:
                        total_chunks += 1
                        continue

                    kg = extract_from_text(
                        text,
                        provider=self.provider,
                        series=series,
                        file=filename,
                        page=page,
                        chunk_id=chunk_id,
                        domain_hint=self.domain_hint,
                    )

                    with kg_jsonl.open("a", encoding="utf-8") as out:
                        out.write(json.dumps({
                            "chunk_id": chunk_id,
                            "file": filename,
                            "page": page,
                            "hash": h,
                            "ts": kg.ts,
                            "entities": kg.entities,
                            "relations": kg.relations
                        }, ensure_ascii=False) + "\n")

                    for e in kg.entities:
                        if e["id"] in dedup_entities:
                            continue
                        dedup_entities.add(e["id"])
                        ents_batch.append(e)
                        total_entities += 1
                        links_batch.append({"eid": e["id"], "cid": chunk_id, "page": page})
                        if len(ents_batch) >= self.batch_upsert:
                            self.db.upsert_entities(ents_batch); ents_batch.clear()

                    for r in kg.relations:
                        key = (r["src"], r["type"], r["dst"])
                        if key in dedup_relations:
                            continue
                        dedup_relations.add(key)
                        rels_batch.append(r)
                        total_relations += 1
                        if len(rels_batch) >= self.batch_upsert:
                            self.db.upsert_relations(rels_batch); rels_batch.clear()

                    total_chunks += 1

        # Insertion entités (batch)
        if ents_batch: 
            self.db.upsert_entities(ents_batch, series=series, approach=approach, build_id=build_id); ents_batch.clear()
            # self.db.upsert_entities(ents_batch); ents_batch.clear()

        # Insertion relations (batch)
        if rels_batch: 
            self.db.upsert_relations(rels_batch, series=series, approach=approach, build_id=build_id); rels_batch.clear()
            # self.db.upsert_relations(rels_batch); rels_batch.clear()
        
        # Liens entités -> chunks (batch): Liens apparitions
        if links_batch: 
            self.db.link_entities_to_chunks(links_batch); links_batch.clear()

        # Stats qualité
        quality = self.db.graph_quality(series=series)
        report["quality"] = quality

        kg_report = {
            "series": series,
            "duration_s": round(time.time() - started, 3),
            "chunks_processed": total_chunks,
            "entities_upserted": total_entities,
            "relations_upserted": total_relations,
            "cache_dir": str(out_dir.relative_to(sdir)),
            "report": report
        }
        (out_dir / "_kg.report.json").write_text(json.dumps(kg_report, ensure_ascii=False, indent=2), encoding="utf-8")
        return kg_report
