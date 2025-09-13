from typing import Any, Dict, Iterable, List
from graph_based.utils.types import EdgeRecord, Community


# ---------------- Cypher GDS ----------------

# CYPHER_1 pour supprimer la projection si elle existe
# (utile pour rebuild partiel)
CYPHER_1 = """
CALL gds.graph.drop($g, false) YIELD graphName
"""

# CYPHER_2 pour créer la projection filtrée sur la série
# (on pourrait aussi utiliser gds.graph.create mais Cypher est plus simple pour filtrer
CYPHER_2 = """CALL gds.graph.project.cypher(
    $graphName,
    'MATCH (n:Entity) RETURN id(n) AS id',
    'MATCH (n:Entity)-[r:RELATED_TO]->(m:Entity) RETURN id(n) AS source, id(m) AS target, r.weight AS weight'
)"""

# CYPHER_3 pour lancer Leiden sur la projection
# (on pourrait aussi utiliser Louvain via gds.louvain.stream)
CYPHER_3 = """
CALL gds.leiden.stream($g, {relationshipWeightProperty: 'weight', resolution:$res, randomSeed: 42})
YIELD nodeId, communityId
RETURN nodeId AS node_id, communityId
"""

# CYPHER_4 pour écrire les communautés + memberships
# (on mappe nodeId -> Node (Entity) puis on MERGE Community + REL
CYPHER_4 = """
UNWIND $rows AS r
        MATCH (e) WHERE id(e) = r.nodeId
        MERGE (c:Community {series: $series, level: $lvl, cid: toString(r.communityId)})
        MERGE (e)-[m:IN_COMMUNITY {series: $series, level: $lvl}]->(c)
"""
# CYPHER_5 pour stats simples (nb communautés + memberships)

CYPHER_5 = """
MATCH (c:Community {series:$series, level:$lvl})
WITH count(c) AS communities
MATCH (:Entity {series:$series})-[m:IN_COMMUNITY {level:$lvl}]->(:Community {series:$series, level:$lvl})
RETURN communities, count(m) AS memberships
"""

# CYPHER_6 pour supprimer la projection (nettoyage)
CYPHER_6 = """CALL gds.graph.drop($g, false)""" # YIELD graphName


def detect(series: str, edges: List[EdgeRecord], *, db, levels: int = 3, resolution: float = 1.2) -> List[Community]:
    """
    Détection de communautés (via GDS Leiden) sur le sous-graphe courant de `series`.
    - Crée (:Community) et (:Entity)-[:IN_COMMUNITY]->(:Community) pour chaque niveau
    - Si edges est vide, lit les edges depuis Neo4j (pour rebuild partiel).
    - Output: [{"id","level","node_ids","parent_id"}...]
    Retourne une liste de dicts [{level, communities:int, memberships:int}]
    """
    gname = f"g_{series}"
    out: List[Dict[str, Any]] = []

    # 1) Projection filtrée sur la série (mode Cypher, plus simple pour filtrer)
    db.run_cypher(CYPHER_1, {"g": gname})  # pas grave si n'existe pas
    db.run_cypher(CYPHER_2, {"g": gname, "series": series})

    # 2) Pour chaque niveau : varier légèrement la résolution (plus haut = communautés plus fines)
    for lvl in range(levels):
        res = resolution * (1.0 + 0.5 * lvl)  # ex: 1.0, 1.5, 2.0 ...
        rows = db.run_cypher(CYPHER_3, {"g": gname, "res": res})

    # 3) Ecriture des communautés + memberships
    #    -> on mappe nodeId -> Node (Entity) puis on MERGE Community + REL
    db.run_cypher(CYPHER_4, {"rows": [dict(row) for row in rows], "series": series, "lvl": lvl})

    stats = db.run_cypher(CYPHER_5, {"series": series, "lvl": lvl}).single()

    out.append({"level": lvl,
                    "communities": int(stats["communities"]),
                    "memberships": int(stats["memberships"])})

    # 4) Nettoyage projection
    db.run_cypher(CYPHER_6, {"g": gname})
    return out