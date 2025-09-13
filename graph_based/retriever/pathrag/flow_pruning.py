# graph_based/retriever/pathrag/flow_pruning.py
from __future__ import annotations
from typing import List, Dict, Any
from itertools import combinations



def _path_score(path: Dict[str, Any], *, alpha: float) -> float:
    """
    Score = alpha^(L-1) * moyenne(conf_nodes U conf_edges)
    """
    L = max(1, int(path.get("length", 1)))
    vals = []
    for n in path.get("nodes", []):
        vals.append(float(n.get("conf", 0.5)))
    for e in path.get("edges", []):
        vals.append(float(e.get("conf", 0.5)))
    base = sum(vals)/len(vals) if vals else 0.5
    return (alpha ** (L-1)) * base


def _extract_path_record(p_row) -> Dict[str, Any]:
    """
    Transforme un résultat Cypher en dict portable.
    On suppose que le cypher renvoie:
      nodes(p) AS ns, relationships(p) AS rs, length(p) AS L
    Avec attributs: id, name, conf, pred/ type, conf.
    """
    ns = p_row["ns"]
    rs = p_row["rs"]
    nodes = [{"id": n.get("id"), "name": n.get("name",""), "conf": float(n.get("conf",0.5))} for n in ns]
    edges = [{"pred": r.get("pred") or r.get("type","REL"), "conf": float(r.get("conf",0.5))} for r in rs]
    return {"nodes": nodes, "edges": edges, "length": int(p_row["L"])}



def topK(series: str, nodes: List[Dict[str, Any]], *, k: int = 12, alpha: float = 0.8, theta: float = 0.05, max_hops: int = 3, db) -> Dict[str, Any]:
    """
    PathRAG 'flow pruning': explore les plus courts chemins entre seeds avec élagage.
    - score chemin S(P) = (1/|E_P|) * sum_{v in P} S(v) ; décroissance par 'alpha' ; seuil 'theta'.
    - Output: [{"nodes":[...], "edges":[...], "score":float, "sources":[cid,...]} ...]
    - NB: renvoie des chemins triés par score ASC pour contrer 'lost-in-the-middle' via le prompt.
    
    Retourne les K chemins les plus 'fiables' (PathRAG light).
    INPUT
      - nodes: [{"id","name","desc","conf","score"}]  (issu de topN)
      - alpha: décroissance par longueur
      - theta: seuil d'élagage (rejette arêtes/noeuds trop incertains)
      - max_hops: longueur max du chemin (>=1)
    OUTPUT
      {
        "paths": [
          {
            "pair": [src_id, dst_id],
            "nodes": [{"id","name","conf"},...],
            "edges": [{"pred","conf"},...],
            "score": float
          }
        ]
      }
    """
    paths: List[Dict[str, Any]] = []
    node_ids = [n["id"] for n in nodes][:30]  # borne
    for src_id, dst_id in combinations(node_ids, 2):
        cypher = f"""
        MATCH (s:Entity {{id:$src, series:$series}}),
              (t:Entity {{id:$dst, series:$series}})
        MATCH p = (s)-[r:REL*1..{int(max_hops)}]-(t)
        WITH p, nodes(p) AS ns, relationships(p) AS rs
        WHERE ALL(n IN ns WHERE coalesce(n.conf,0.5) >= $theta)
          AND ALL(e IN rs WHERE coalesce(e.conf,0.5) >= $theta)
        RETURN ns AS ns, rs AS rs, length(p) AS L
        LIMIT 6
        """
        for row in db.run_cypher(cypher, {"src": src_id, "dst": dst_id, "series": series, "theta": float(theta)}):
            rec = _extract_path_record(row)
            score = _path_score(rec, alpha=alpha)
            rec["pair"] = [src_id, dst_id]
            rec["score"] = float(score)
            paths.append(rec)

    # Top-K global
    paths.sort(key=lambda x: x["score"], reverse=True)
    return {"paths": paths[:k]}