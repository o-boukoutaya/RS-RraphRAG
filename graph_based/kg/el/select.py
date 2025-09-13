# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Optional
import json

from graph_based.kg.el import candidates

def choose(series: str, cand_map: Dict[str, List[Dict[str, Any]]], *, provider) -> Dict[str, Optional[str]]:
    """
    Sélection finale par LLM 'multi-choice' avec option 'None'. (Sélection multi-critères très simple : score dense * bonus lexical.)
    - Output: mapping mention_id -> node_id retenu | None (Retourne l'id gagnant, ou None si les scores sont faibles).
    """
    candidates = cand_map.get(series, [])
    allowed_types = list(set(c.get("type") for c in candidates if c.get("type")))
    context = " ".join(d["context"] for d in candidates if d.get("context"))
    return mrc_select_best_or_none(series, allowed_types, context=context, candidates=candidates, llm_chat_fn=provider.chat, allow_none=True)


def mrc_select_best_or_none(mention: str, allowed_types: List[Any|None], context: str,
                            candidates: List[Dict], llm_chat_fn=None,
                            allow_none: bool = True, thresh: float = 0.55) -> Dict:
    """
        Sélection MRC-style (LLM) avec fallback heuristique.
        - Construit un prompt JSON (compatible avec app/prompts/el_entgpt.md) pour LLM.
        - Si l’LLM n’est pas encore branché → fallback: top by final_score, seuil.
        Retourne: {"mention":..., "chosen_id": "...|NONE", "rationale": "...", "considered":[...]}
    """
    payload = {
        "mention": mention,
        "context": context[:400],
        "allowed_types": allowed_types,
        "candidates": {
            "prior": [{"id":c["id"], "label":c["label"], "score":float(c.get("prior",0.0))} for c in candidates[:10]],
            "dense": [{"id":c["id"], "label":c["label"], "score":float(c.get("dense",0.0))} for c in candidates[:10]],
        }
    }
    # 1) Si LLM dispo → déléguer
    if llm_chat_fn is not None:
        sys = "You are an entity disambiguation specialist. Always return JSON."
        user = json.dumps(payload, ensure_ascii=False)
        try:
            raw = llm_chat_fn(sys, user)
            js = json.loads(raw)
            if "chosen_id" in js:
                return js
        except Exception:
            pass

    # 2) Fallback heuristique (robuste en dev)
    sorted_c = sorted(candidates, key=lambda x: x.get("final_score", x.get("score", 0.0)), reverse=True)
    if not sorted_c:
        return {"mention": mention, "chosen_id": "NONE", "rationale": "no candidates", "considered": []}
    top = sorted_c[0]
    if float(top.get("final_score", top.get("score", 0.0))) < thresh and allow_none:
        return {"mention": mention, "chosen_id": "NONE", "rationale": "low confidence", "considered": sorted_c[:5]}
    return {"mention": mention, "chosen_id": top["id"], "rationale": "highest final_score", "considered": sorted_c[:5]}
