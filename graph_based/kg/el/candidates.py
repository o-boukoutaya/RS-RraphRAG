# -*- coding: utf-8 -*-

"""
Génération de candidats (PRIOR + DENSE).
- PRIOR: score lexical naïf (overlap de tokens) pour ne pas dépendre d'un moteur externe.
- DENSE: cosine entre embeddings du label et des nœuds (via kg/build/embeddings.py).
Branchable: remplacez les fonctions par votre BM25/FAISS/Qdrant.
"""

from __future__ import annotations
from typing import List, Tuple, Dict, Any
from collections import Counter
import math
from graph_based.utils.types import NodeRecord, EdgeRecord, Community, BuildReport, Summary


# def generate(series: str, nodes: List[NodeRecord], *, db, provider, k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
#     """
#     Génère pour chaque mention/non-canon un top-k de candidats d'entités existantes.
#     - Output: mapping mention_id -> [{"node_id","label","score"}...]
#     """
    

def _tokenize(s: str) -> List[str]:
    return [t for t in (s or "").lower().replace("-", " ").split() if t]

def _cos(a: List[float], b: List[float]) -> float:
    if not a or not b: return 0.0
    s = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return s / ((na*nb) or 1.0)

def prior_candidates(mention: str, allowed_types: List[str], catalog_nodes: List[Dict], topk: int = 20) -> List[Dict]:
    mtoks = Counter(_tokenize(mention))
    scored = []
    for n in catalog_nodes:
        if allowed_types and n.get("type") not in allowed_types:
            continue
        rtoks = Counter(_tokenize(n.get("label","")))
        inter = sum((mtoks & rtoks).values())
        uni = sum((mtoks | rtoks).values()) or 1
        jacc = inter / uni
        if jacc > 0.0:
            scored.append({"id": n["id"], "label": n.get("label",""), "type": n.get("type",""), "score": jacc})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:topk]

def dense_candidates(mention_vec: List[float], catalog_nodes: List[Dict], topk: int = 20) -> List[Dict]:
    scored = []
    for n in catalog_nodes:
        c = _cos(mention_vec, n.get("vec") or [])
        scored.append({"id": n["id"], "label": n.get("label",""), "type": n.get("type",""), "score": c})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:topk]

def merge_candidates(prior: List[Dict], dense: List[Dict], w_prior: float = 0.5, w_dense: float = 0.5, topk: int = 30) -> List[Dict]:
    by_id: Dict[str, Dict] = {}
    for s in prior:
        by_id.setdefault(s["id"], {"id": s["id"], "label": s["label"], "type": s.get("type","")})["prior"] = s["score"]
    for s in dense:
        by_id.setdefault(s["id"], {"id": s["id"], "label": s["label"], "type": s.get("type","")})["dense"] = s["score"]
    out = []
    for nid, d in by_id.items():
        p = d.get("prior", 0.0); v = d.get("dense", 0.0)
        out.append({**d, "score": w_prior*p + w_dense*v, "prior": p, "dense": v})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:topk]