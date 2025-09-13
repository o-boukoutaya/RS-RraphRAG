# adapters/db/cypher.py
from __future__ import annotations

# ---------- Schémas ----------
BASE_SCHEMA = [
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE INDEX chunk_series IF NOT EXISTS FOR (c:Chunk) ON (c.series)",

    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    "CREATE FULLTEXT INDEX entity_name_ft IF NOT EXISTS FOR (e:Entity) ON EACH [e.name]"
]

def vector_index_create(name: str, label="Chunk", prop="embedding") -> str:
    return f"""
    CREATE VECTOR INDEX {name} IF NOT EXISTS
    FOR (n:{label}) ON (n.{prop})
    OPTIONS {{
      indexConfig: {{
        `vector.dimensions`: $dim,
        `vector.similarity_function`: $sim
      }}
    }}
    """

VECTOR_INDEX_EXISTS = """
SHOW INDEXES YIELD name, type
WHERE type = 'VECTOR' AND name = $name
RETURN count(*) AS c
"""

# ---------- Ingestion (Chunks) ----------
UPSERT_CHUNKS = """
UNWIND $rows AS row
MERGE (c:Chunk {id: row.id})
SET   c.series     = coalesce(row.series, c.series),
      c.doc_id     = row.doc_id,
      c.page       = row.page,
      c.text       = row.text,
      c.meta_json  = row.meta_json,
      c.approach   = row.approach,
      c.build_id   = row.build_id
FOREACH (vec IN CASE WHEN row.embedding IS NULL THEN [] ELSE [row.embedding] END |
    SET c.embedding = vec)
RETURN count(c) AS n
"""

GET_CHUNKS_BY_SERIES_OLD = """
MATCH (c:Chunk)
WHERE c.series = $series
RETURN c
"""

GET_CHUNKS_BY_SERIES = """
MATCH (c:Chunk)
WHERE c.series = $series
RETURN c.id AS cid,
       c.text AS text,
       coalesce(c.meta_json, "{}") AS meta
ORDER BY c.id
"""

# ---------- Similarité ----------
QUERY_TOP_K = """
CALL db.index.vector.queryNodes($index, $k, $vec)
YIELD node, score
RETURN elementId(node) AS eid, labels(node) AS labels, node.id AS id,
       node.name AS name, node.text AS text, score
"""

# ---------- KG : entités/relations ----------
UPSERT_ENTITIES = """
UNWIND $rows AS row
MERGE (e:Entity {id: row.id})
SET  e.name       = row.name,
     e.type       = row.type,
     e.series     = coalesce(row.series, e.series),
     e.source     = coalesce(row.source, e.source),
     e.attrs_json = row.attrs_json,
     e.meta_json  = row.meta_json,
     e.approach   = row.approach,
     e.build_id   = row.build_id
FOREACH (vec IN CASE WHEN row.embedding IS NULL THEN [] ELSE [row.embedding] END |
    SET e.embedding = vec)
RETURN count(e) AS n
"""

UPSERT_RELATIONS = """
UNWIND $rows AS row
MATCH (s:Entity {id: row.src}), (t:Entity {id: row.dst})
MERGE (s)-[r:REL {id: row.id}]->(t)
SET   r.kind      = row.kind,
      r.series    = row.series,
      r.weight    = row.weight,
      r.meta_json = row.meta_json,
      r.approach  = row.approach,
      r.build_id  = row.build_id
RETURN count(r) AS n
"""

LINK_ENTS_TO_CHUNKS = """
UNWIND $links AS l
MATCH (e:Entity {id: l.eid})
MATCH (c:Chunk  {id: l.cid})
MERGE (e)-[r:APPEARS_IN {page: l.page}]->(c)
RETURN count(r) AS n
"""

# ---------- Qualité / Stats ----------
GRAPH_STATS = """
RETURN
  toInteger({{
    entities:  size([() WHERE () IS NOT NULL | 1]) // placeholder, remplacé en python
  }}) AS dummy
"""

COUNT_ENTITIES_BY = """
MATCH (e:Entity)
WHERE $series IS NULL OR e.series = $series
RETURN count(e) AS entities
"""

COUNT_RELATIONS_BY = """
MATCH ()-[r:REL]->()
WHERE $series IS NULL OR r.series = $series
RETURN count(r) AS relations
"""

COUNT_ORPHAN_RELATIONS = """
MATCH ()-[r:REL]->()
WHERE $series IS NULL OR r.series = $series
AND (startNode(r) IS NULL OR endNode(r) IS NULL)
RETURN count(r) AS orphans
"""

COUNT_DUP_ENTITY_IDS = """
MATCH (e:Entity)
WITH e.id AS id, count(*) AS c
WHERE c > 1
RETURN count(*) AS dup_ids
"""

# Entités isolées (aucune arête incidente) — utile pour évaluer la couverture du KG :
COUNT_ENTITIES_ISOLATED = """
MATCH (e:Entity)
WHERE ($series IS NULL OR e.series = $series)
  AND NOT (e)--()
RETURN count(e) AS isolated_entities
"""

# Relations hors-série (lorsqu’on filtre par series, compter les relations dont au moins une extrémité ou la relation elle-même n’a pas la même series) :
COUNT_OFFSERIES_RELATIONS = """
MATCH (s:Entity)-[r:REL]->(t:Entity)
WHERE $series IS NOT NULL
  AND (
       coalesce(s.series,'') <> $series
    OR coalesce(t.series,'') <> $series
    OR coalesce(r.series,'') <> $series
  )
RETURN count(r) AS offseries_relations
"""