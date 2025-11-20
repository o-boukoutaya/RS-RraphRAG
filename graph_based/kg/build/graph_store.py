from typing import Any, Dict, Iterable, List, Optional, Tuple
from collections import defaultdict
from app.observability.pipeline import pipeline_step
from graph_based.utils.types import NodeRecord, EdgeRecord
from app.core.resources import get_db


# ---------------- Contraintes (à exécuter une fois) ----------------
# On peut les installer idempotentes à l’initialisation (ou tout en bas de graph_store.upsert avec un drapeau mémoire). 
# Utilise la syntaxe Neo4j 4.x+ ou 5.x+ suivant ta version.

CONTRAINT_1_4X = """CREATE CONSTRAINT IF NOT EXISTS ON (e:Entity)  ASSERT e.id IS UNIQUE;"""
CONTRAINT_2_4X = """CREATE CONSTRAINT IF NOT EXISTS ON (c:Chunk)   ASSERT c.id IS UNIQUE;"""
CONTRAINT_3_4X = """CREATE CONSTRAINT IF NOT EXISTS ON ()-[r:REL]-() ASSERT r.id IS UNIQUE;"""

CONTRAINT_1_5X = """CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;"""
CONTRAINT_2_5X = """CREATE CONSTRAINT chunk_id  IF NOT EXISTS FOR (c:Chunk)  REQUIRE c.id IS UNIQUE;"""
CONTRAINT_3_5X = """CREATE CONSTRAINT rel_id    IF NOT EXISTS FOR ()-[r:REL]-() REQUIRE r.id IS UNIQUE;"""

@pipeline_step("Graph Build - Ensure Constraints")
def ensure_constraints(*, db) -> None:
    # for q_4x in [CONTRAINT_1_4X, CONTRAINT_2_4X, CONTRAINT_3_4X]:
    for q_5x in [CONTRAINT_1_5X, CONTRAINT_2_5X, CONTRAINT_3_5X]:
        try:
            db.run_cypher(q_5x)
        except Exception:
            pass  # a ignorer si version 4.x ; dans ce cas utiliser le triplet 'ON (...) ASSERT ...'

# ---------------- Cypher d’upsert (UNWIND) ----------------

# NODES
CUPSERT_ENTITIES = """UNWIND $rows AS r
MERGE (e:Entity {id: r.id})
  ON CREATE SET e.series = $series, e.name = r.name, e.type = r.type,
                e.aliases = coalesce(r.aliases, []), e.desc = coalesce(r.desc, ""),
                e.conf = coalesce(r.conf, 0.0)
  ON MATCH  SET e.name   = r.name,
                e.type   = r.type,
                e.aliases = apoc.coll.toSet(coalesce(e.aliases, []) + coalesce(r.aliases, [])),
                e.desc   = CASE WHEN size(coalesce(r.desc,"")) > size(coalesce(e.desc,"")) THEN r.desc ELSE e.desc END,
                e.conf   = CASE WHEN r.conf > e.conf THEN r.conf ELSE e.conf END;
"""

# RELS
CUPSERT_RELATIONS = """UNWIND $rels AS r
MATCH (s:Entity {id: r.src_id})
MATCH (o:Entity {id: r.dst_id})
MERGE (s)-[e:REL {id: r.id}]->(o)
  ON CREATE SET e.series = $series, e.pred = r.pred, e.cids = coalesce(r.cids, []),
                e.conf = coalesce(r.conf, 0.0)
  ON MATCH  SET e.pred = r.pred,
                e.cids = apoc.coll.toSet(coalesce(e.cids, []) + coalesce(r.cids, [])),
                e.conf = CASE WHEN r.conf > e.conf THEN r.conf ELSE e.conf END;
"""

# # NODES
# CUPSERT_ENTITIES = """
# UNWIND $rows AS r
# MERGE (e:Entity {id: r.id})
# ON CREATE SET
#   e.series = $series,
#   e.name   = r.name,
#   e.type   = r.type,
#   e.aliases = coalesce(r.aliases, []),
#   e.desc    = coalesce(r.desc, ""),
#   e.cids    = coalesce(r.cids, []),
#   e.conf    = coalesce(r.conf, 0.0)
# ON MATCH SET
#   e.series = $series,
#   e.name   = r.name,
#   e.type   = r.type,
#   e.desc   = CASE WHEN size(coalesce(r.desc,"")) > size(coalesce(e.desc,""))
#                   THEN r.desc ELSE e.desc END,
#   e.conf   = CASE WHEN r.conf > e.conf THEN r.conf ELSE e.conf END,
#   e.aliases =
#     reduce(acc = [], x IN (coalesce(e.aliases, []) + coalesce(r.aliases, [])) |
#           CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END),
#   e.cids =
#     reduce(acc = [], x IN (coalesce(e.cids, []) + coalesce(r.cids, [])) |
#           CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END)
# RETURN count(*) AS n;
# """

# # RELS
# CUPSERT_RELATIONS = """
# UNWIND $rels AS r
# MATCH (s:Entity {id: r.src_id})
# MATCH (o:Entity {id: r.dst_id})
# MERGE (s)-[e:REL {id: r.id}]->(o)
# ON CREATE SET
#   e.series = $series,
#   e.pred   = r.pred,
#   e.cids   = coalesce(r.cids, []),
#   e.conf   = coalesce(r.conf, 0.0)
# ON MATCH SET
#   e.pred = r.pred,
#   e.conf = CASE WHEN r.conf > e.conf THEN r.conf ELSE e.conf END,
#   e.cids =
#     reduce(acc = [], x IN (coalesce(e.cids, []) + coalesce(r.cids, [])) |
#           CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END)
# RETURN count(*) AS n;
# """

# // OPTIONAL: traces de mentions (mutual-indexing)
LINK_MENTIONS = """
UNWIND $rows AS r
UNWIND coalesce(r.cids, []) AS cid
MATCH (e:Entity {id: r.id})
MATCH (c:Chunk  {id: cid})
MERGE (e)-[:MENTIONED_IN]->(c);
"""
from app.observability.pipeline import pipeline_step
@pipeline_step("Graph Build - Upsert")
def upsert(series: str, nodes: List[NodeRecord], edges: List[EdgeRecord]) -> Dict[str, Any]:
    """
    Upsert transactionnel dans Neo4j (étiquettes: series, types d’entités, types de relations).
    - Output: {"nodes_upserted": int, "edges_upserted": int}
    """
    # database et provider LLM depuis resources
    db = get_db()

    # Préparer des "rows" sûrs (types JSON-compatibles)
    safe_nodes = [{
        "id": n["id"], 
        "name": n["name"], 
        "type": n["type"],
        "aliases": list(n.get("aliases", []))[:20],
        "desc": str(n.get("desc",""))[:500],
        "cids": list(n.get("cids", []))[:200],
        "conf": float(n.get("conf", 0.0)),
    } for n in nodes]

    safe_edges = [{
        "id": e["id"], "src_id": e["src_id"], "dst_id": e["dst_id"],
        "pred": e["pred"], "cids": list(e.get("cids", []))[:200],
        "conf": float(e.get("conf", 0.0)),
    } for e in edges]

    # Exécuter via l’adapter (même pattern qu'upsert_chunks et stream_chunks)
    # Idéalement exposez un helper db.run(cypher:str, **params). Sinon, reproduisez
    # le pattern 'with self._session() as s: s.run(...)' dans une méthode dédiée.
    n_count = get_db().run_cypher(CUPSERT_ENTITIES, {"rows": safe_nodes, "series": series})
    r_count = get_db().run_cypher(CUPSERT_RELATIONS, {"rels": safe_edges, "series": series})
    print(f"[UPSERT] entities={len(safe_nodes)} rels={len(safe_edges)} | neo4j: nodes={n_count} rels={r_count}")

    # mutual-indexing mentions (optionnel)
    get_db().run_cypher(LINK_MENTIONS, {"rows": safe_nodes, "series": series})

    return {
        "series": series,
        "nodes_written": len(safe_nodes),
        "rels_written": len(safe_edges),
    }