from typing import Dict, List, Tuple, Any
from graph_based.utils.types import Community


CYPHER_PARENT = """
MATCH (cLo:Community {series:$series, level:$lo})<-[:IN_COMMUNITY {series:$series, level:$lo}]-(e:Entity {series:$series})
        MATCH (e)-[:IN_COMMUNITY {series:$series, level:$hi}]->(cHi:Community {series:$series, level:$hi})
        WITH cLo, cHi, count(e) AS overlap
        WHERE overlap > 0
        MERGE (cLo)-[p:PARENT {series:$series, from:$lo, to:$hi}]->(cHi)"""

CYPHER_COUNT = """
MATCH (:Community {series:$series, level:$lo})-[p:PARENT {series:$series, from:$lo, to:$hi}]->(:Community {series:$series, level:$hi})
        RETURN count(p) AS n
"""

from app.observability.pipeline import pipeline_step
@pipeline_step("Graph Build - Community Hierarchy Wiring")
def wire(series: str, communities: List[Community], *, db) -> Dict[str, Any]:
    """
    Écrit les communautés + relations parent->enfant en base (si pas déjà fait).
    Pour chaque paire de niveaux consécutifs (l -> l+1), crée les arêtes PARENT en fonction du chevauchement d'entités (comptage des membres communs).
    (:Community)-[:PARENT {series, from, to, overlap}]->(:Community).
    - Output: {"communities_written": int}
    """
    # Paire de niveaux présents dans `communities`
    levels = sorted({c["level"] for c in communities})
    created = 0


    for lo, hi in zip(levels[:-1], levels[1:]):
        db.run_cypher(CYPHER_PARENT, {"series": series, "lo": lo, "hi": hi})

        n = db.run_cypher(CYPHER_COUNT, {"series": series, "lo": lo, "hi": hi}).single()["n"]
        created += n

    return {"series": series, "parent_edges": int(created)}