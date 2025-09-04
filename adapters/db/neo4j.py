# adapters/db/neo4j.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
import contextlib, json, logging

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import Neo4jError

from app.core.config import get_settings
from . import cypher as C

log = logging.getLogger("neo4j")

# ------------------ Helpers ------------------

def _json_dump(x: Any) -> str:
    if x is None:
        return "{}"
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return "{}"

def _now_ms() -> int:
    import time
    return int(time.time() * 1000)

# ------------------ Adapter ------------------

@dataclass
class Neo4jAdapter:
    uri: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

    # logging Cypher (optionnel)
    _log_file: Optional[Path] = None
    _driver: Driver = None  # type: ignore

    def __post_init__(self) -> None:
        cfg = get_settings().neo4j
        self.uri = self.uri or cfg.uri
        self.user = self.user or cfg.username
        self.password = self.password or cfg.password
        self.database = self.database or getattr(cfg, "database", None)

        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.ensure_base_schema()

    # ---------- Sessions ----------
    def _session(self):
        return self._driver.session(database=self.database) if self.database else self._driver.session()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._driver.close()

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.close()
    def ping(self) -> bool:
        try:
            with self._session() as s:
                s.run("RETURN 1").consume()
            return True
        except Neo4jError as ex:
            log.error("Neo4j ping failed: %s", ex)
            return False

    # ---------- Cypher logging ----------
    def enable_query_logging(self, log_path: Path) -> None:
        """Active l’écriture JSONL des requêtes (Cypher + params)."""
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = log_path
        log.info("Neo4j query logging -> %s", log_path)

    def _log_cypher(self, q: str, params: Mapping[str, Any]) -> None:
        if not self._log_file:
            return
        rec = {"ts": _now_ms(), "query": q, "params": params}
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- Schéma ----------
    def ensure_base_schema(self) -> None:
        """Crée les contraintes d’unicité de base."""
        with self._driver.session() as s:
            for qi in C.BASE_SCHEMA:
                try:
                    s.run(qi).consume()
                except Exception as ex:
                    log.info("Schema notice: %s", ex)

    # ---------- Index vectoriel ----------
    def check_index_exists(self, name: str) -> bool:
        with self._session() as s:
            rec = s.run(C.VECTOR_INDEX_EXISTS, name=name).single()
            return bool(rec and rec["c"] > 0)

    def create_vector_index(self, name: str, *, label="Chunk", prop="embedding",
                            dimensions: int = 1536, similarity="cosine") -> None:
        q = C.vector_index_create(name, label, prop)
        params = {"dim": int(dimensions), "sim": similarity}
        self._log_cypher(q, params)
        with self._session() as s:
            s.run(q, **params).consume()

    # ---------- Ingestion : Chunks ----------
    def upsert_chunks(self, rows: Sequence[Mapping[str, Any]],
                      *, series: Optional[str] = None,
                      approach: Optional[str] = None,
                      build_id: Optional[str] = None) -> int:
        safe: List[Dict[str, Any]] = []
        for r in rows:
            safe.append({
                "id": r["id"],
                "series": r.get("series") or series,
                "doc_id": r.get("doc_id"),
                "page": r.get("page"),
                "text": r.get("text") or "",
                "meta_json": _json_dump(r.get("meta")),
                "embedding": r.get("embedding"),
                "approach": r.get("approach") or approach,
                "build_id": r.get("build_id") or build_id,
            })
        q, params = C.UPSERT_CHUNKS, {"rows": safe}
        self._log_cypher(q, params)
        with self._session() as s:
            return int(s.run(q, **params).single()["n"])

    # ---------- Similarité ----------
    def query_top_k(self, index_name: str, query_vec: Sequence[float], k: int = 5) -> List[Dict[str, Any]]:
        q, params = C.QUERY_TOP_K, {"index": index_name, "k": int(k), "vec": list(query_vec)}
        self._log_cypher(q, params)
        with self._session() as s:
            res = s.run(q, **params)
            return [r.data() for r in res]

    # ---------- KG : entités ----------
    def upsert_entities(self, rows: Sequence[Mapping[str, Any]],
                        *, series: Optional[str] = None,
                        approach: Optional[str] = None,
                        build_id: Optional[str] = None) -> int:
        safe: List[Dict[str, Any]] = []
        for r in rows:
            safe.append({
                "id": r["id"],
                "name": r.get("name"),
                "type": r.get("type") or "Unknown",
                "series": r.get("series") or series,
                "source": r.get("source"),
                "attrs_json": _json_dump(r.get("attrs")),
                "meta_json": _json_dump(r.get("meta")),
                "embedding": r.get("embedding"),
                "approach": r.get("approach") or approach,
                "build_id": r.get("build_id") or build_id,
            })
        q, params = C.UPSERT_ENTITIES, {"rows": safe}
        self._log_cypher(q, params)
        with self._session() as s:
            return int(s.run(q, **params).single()["n"])

    # ---------- KG : relations ----------
    def upsert_relations(self, rows: Sequence[Mapping[str, Any]],
                         *, series: Optional[str] = None,
                         approach: Optional[str] = None,
                         build_id: Optional[str] = None) -> int:
        safe: List[Dict[str, Any]] = []
        for r in rows:
            rid = r.get("id") or f"{r['src']}::{r.get('type','REL')}::{r['dst']}"
            safe.append({
                "id": rid,
                "src": r["src"],
                "dst": r["dst"],
                "kind": r.get("type") or "REL",
                "series": r.get("series") or series,
                "weight": float(r.get("weight", 1.0)),
                "meta_json": _json_dump(r.get("meta")),
                "approach": r.get("approach") or approach,
                "build_id": r.get("build_id") or build_id,
            })
        q, params = C.UPSERT_RELATIONS, {"rows": safe}
        self._log_cypher(q, params)
        with self._session() as s:
            return int(s.run(q, **params).single()["n"])

    # ---------- Traçabilité entité->chunk ----------
    def link_entities_to_chunks(self, links: Sequence[Mapping[str, Any]]) -> int:
        q, params = C.LINK_ENTS_TO_CHUNKS, {"links": list(links)}
        self._log_cypher(q, params)
        with self._session() as s:
            rec = s.run(q, **params).single()
            return int(rec["n"]) if rec else 0

    # ---------- Qualité ----------
    # def graph_quality(self, *, series: Optional[str] = None) -> Dict[str, int]:
    #     with self._session() as s:
    #         ents = s.run(C.COUNT_ENTITIES_BY, series=series).single()["entities"]
    #         rels = s.run(C.COUNT_RELATIONS_BY, series=series).single()["relations"]
    #         orph = s.run(C.COUNT_ORPHAN_RELATIONS, series=series).single()["orphans"]
    #         dups = s.run(C.COUNT_DUP_ENTITY_IDS).single()["dup_ids"]
    #     return {"entities": int(ents), "relations": int(rels), "orphans": int(orph), "dup_entity_ids": int(dups)}

    def graph_quality(self, *, series: Optional[str] = None) -> Dict[str, int]:
        with self._session() as s:
            ents = s.run(C.COUNT_ENTITIES_BY, series=series).single()["entities"]
            rels = s.run(C.COUNT_RELATIONS_BY, series=series).single()["relations"]
            isolated = s.run(C.COUNT_ENTITIES_ISOLATED, series=series).single()["isolated_entities"]
            offseries = s.run(C.COUNT_OFFSERIES_RELATIONS, series=series).single().get("offseries_relations", 0)
        return {
            "entities": int(ents),
            "relations": int(rels),
            "isolated_entities": int(isolated),
            "offseries_relations": int(offseries),
        }

# Fabrique
def client_from_settings() -> Neo4jAdapter:
    return Neo4jAdapter()
