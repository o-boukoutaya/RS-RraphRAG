import re
from typing import Any, Dict, Iterable, List
from graph_based.utils.types import EdgeRecord, Community
from app.core.resources import get_db, get_provider


# ---------------- Cypher GDS ----------------

# CYPHER_1 pour supprimer la projection si elle existe (utile pour rebuild partiel)
# Drop conditionnel (ok si le graph n'existe pas)
CYPHER_1 = """
CALL gds.graph.exists($graphName) YIELD exists
WITH exists
CALL apoc.do.when(
  exists,
  'CALL gds.graph.drop($graphName,false) YIELD graphName RETURN graphName AS name',
  'RETURN $g AS name',
  {g:$graphName}
) YIELD value
RETURN value.name AS name
"""
# CYPHER_1 = """
# CALL gds.graph.drop($graphName, false) YIELD graphName
# """

# CYPHER_2 pour créer la projection filtrée sur la série : UNDIRECTED (Leiden req)
# (on pourrait aussi utiliser gds.graph.create mais Cypher est plus simple pour filtrer
# Projection cypher filtrée par série
CYPHER_2 = """
CALL gds.graph.project.cypher(
  $graphName,
  'MATCH (n:Entity {series: $series}) RETURN id(n) AS id',
  'MATCH (n:Entity {series: $series})-[r:REL]->(m:Entity {series: $series})
   RETURN id(n) AS source, id(m) AS target, coalesce(r.conf,1.0) AS conf',
  { undirectedRelationshipTypes: ["*"] } 
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
"""
# CYPHER_2 = """
# CALL gds.graph.project.cypher(
#   $graphName,
#   'MATCH (n:Entity)          WHERE n.series = $series
#    RETURN id(n) AS id',
#   'MATCH (s:Entity)-[r:REL]->(t:Entity)
#    WHERE s.series = $series AND t.series = $series AND r.series = $series
#    RETURN id(s) AS source, id(t) AS target, coalesce(r.conf, 1.0) AS weight',
#   { parameters: { series: $series } }
# )
# YIELD graphName, nodeCount, relationshipCount
# """
# CYPHER_2 = """CALL gds.graph.project.cypher(
#     $graphName,
#     'MATCH (n:Entity) RETURN id(n) AS id',
#     'MATCH (n:Entity)-[r:RELATED_TO]->(m:Entity) RETURN id(n) AS source, id(m) AS target, r.weight AS weight'
# )"""

# CYPHER_3 pour lancer Leiden sur la projection
# (on pourrait aussi utiliser Louvain via gds.louvain.stream)
# Leiden (poids = 'weight')
CYPHER_3 = """
CALL gds.leiden.stream(
  $graphName,
  { relationshipWeightProperty: "conf", gamma: $gamma, concurrency: 4 }
)
YIELD nodeId, communityId
RETURN nodeId AS node_id, communityId
"""
# CYPHER_3 = """
# CALL gds.leiden.stream(
#   $graphName, {relationshipWeightProperty:'weight', resolution:$res, randomSeed:42}
# )
# YIELD nodeId, communityId
# RETURN nodeId AS nodeId, communityId AS communityId
# """
# CYPHER_3 = """
# CALL gds.leiden.stream($graphName, {relationshipWeightProperty: 'weight', gamma:$res})
# YIELD nodeId, communityId
# RETURN nodeId AS nodeId, communityId
# """

# CYPHER_4 pour écrire les communautés + memberships
# (on mappe nodeId -> Node (Entity) puis on MERGE Community + REL
CYPHER_4 = """
UNWIND $rows AS r
        MATCH (e:Entity) WHERE id(e) = r.nodeId
        MERGE (c:Community {series: $series, level: $lvl, cid: toString(r.communityId)})
        MERGE (e)-[m:IN_COMMUNITY {series: $series, level: $lvl}]->(c)
"""

# CYPHER_5 pour stats simples (nb communautés + memberships)
# 5) Stats
CYPHER_5 = """
MATCH (c:Community {series:$series, level:$lvl})
WITH count(c) AS communities
MATCH (:Entity {series:$series})-[:IN_COMMUNITY {level:$lvl}]->(:Community {series:$series, level:$lvl})
RETURN communities, count(*) AS memberships
"""

# CYPHER_6 pour supprimer la projection (nettoyage)
CYPHER_6 = "CALL gds.graph.drop($graphName,false) YIELD graphName RETURN graphName"

def detect(series: str, levels: int = 3, resolution: float = 1.2) -> List[Community]:
    """
    Détection de communautés (via GDS Leiden) sur le sous-graphe courant de `series`.
    - Crée (:Community) et (:Entity)-[:IN_COMMUNITY]->(:Community) pour chaque niveau
    - Si edges est vide, lit les edges depuis Neo4j (pour rebuild partiel).
    - Output: [{"id","level","node_ids","parent_id"}...]
    Retourne une liste de dicts [{level, communities:int, memberships:int}]
    """
    # database et provider LLM depuis resources
    db = get_db()

    gname = f"g_{re.sub(r'[^A-Za-z0-9_]', '_', series)}" # gname = f"g_{series}"
    out: List[Dict[str, Any]] = []

    # 1) Projection filtrée sur la série (mode Cypher, plus simple pour filtrer)
    result_c1 = db.run_cypher(CYPHER_1, {"graphName": gname})  # pas grave si n'existe pas
    result_c2 = db.run_cypher(CYPHER_2, {"graphName": gname, "series": series})
    result_c3 = db.run_cypher(CYPHER_3, {"graphName": gname, "gamma": resolution * (1.0 + 0.5 * 1)})
    return [result_c1, result_c2, result_c3]
    # return [result_c3]

    # 2) Pour chaque niveau : varier légèrement la résolution (plus haut = communautés plus fines)
    # for lvl in range(levels):
    #     res = resolution * (1.0 + 0.5 * lvl)  # ex: 1.0, 1.5, 2.0 ...
    #     rows = db.run_cypher(CYPHER_3, {"graphName": gname, "res": res})

    # return rows

    # # 3) Ecriture des communautés + memberships
    # #    -> on mappe nodeId -> Node (Entity) puis on MERGE Community + REL
    # db.run_cypher(CYPHER_4, {"rows": [dict(row) for row in rows], "series": series, "lvl": lvl})

    # stats = db.run_cypher(CYPHER_5, {"series": series, "lvl": lvl}).single()

    # out.append({"level": lvl,
    #                 "communities": int(stats["communities"]),
    #                 "memberships": int(stats["memberships"])})

    # # 4) Nettoyage projection
    # db.run_cypher(CYPHER_6, {"graphName": gname})
    # return out