# graph_based/retriever/pathrag/node_retrieval.py
from __future__ import annotations
from typing import List, Dict, Any
import re


def _keywords(q: str) -> List[str]:
    toks = re.findall(r"[A-Za-zÀ-ÿ0-9\-]+", q.lower())
    return [t for t in toks if len(t) >= 3]

# def topN(series: str, query: str, *, db, provider, N: int = 30) -> List[Tuple[str, float]]:
def topN(series: str, query: str, *, n: int = 30, db) -> Dict[str, Any]:
    """
    Récupère N noeuds 'seed' pertinents (mix: nom/desc + mutual-index chunks).
    - Output: [(node_id, score), ...]

    Retourne les N meilleurs nœuds (entités) candidats pour PathRAG.
    INPUT
      - series, query, db
    OUTPUT
      {
        "nodes": [
          {"id": str, "name": str, "desc": str, "conf": float, "score": float}
        ]
      }
    Hypothèses de schéma: (:Entity {id, series, name, aliases, desc, conf})
    Stratégie: matching lex. sur name/aliases + score simple (overlap + conf).
    """
    kws = _keywords(query)
    if not kws:
        kws = [query.lower()]
    # Cypher naïf: concatène des predicates CONTAINS
    # (évite d'imposer un index externe ici)
    where_parts = []
    params = {"series": series}
    for i, kw in enumerate(kws[:8]):  # borne de sécurité
        p = f"kw{i}"
        params[p] = kw
        where_parts.append(f"toLower(e.name) CONTAINS ${p} OR any(a IN coalesce(e.aliases,[]) WHERE toLower(a) CONTAINS ${p})")
    cypher = f"""
    MATCH (e:Entity {{series:$series}})
    WHERE {' OR '.join(where_parts)}
    RETURN e.id AS id, e.name AS name, e.desc AS desc, coalesce(e.conf,0.5) AS conf
    LIMIT 400
    """
    rows = [r for r in db.run_cypher(cypher, params)]

    def score_row(r: Dict[str, Any]) -> float:
        name = (r.get("name") or "").lower()
        desc = (r.get("desc") or "").lower()
        occ = sum(1 for k in kws if (k in name or k in desc))
        return occ + float(r.get("conf", 0.5))

    nodes = []
    for r in rows:
        nodes.append({
            "id": r["id"],
            "name": r.get("name",""),
            "desc": r.get("desc",""),
            "conf": float(r.get("conf",0.5)),
            "score": score_row(r),
        })
    nodes.sort(key=lambda x: x["score"], reverse=True)
    return {"nodes": nodes[:n]}