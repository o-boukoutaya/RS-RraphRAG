# graph_based/kg/summarize/qfs_reduce.py
from __future__ import annotations
from typing import List, Dict, Any
import json, re
from pathlib import Path
from graph_based.utils.tokenize import fit
from graph_based.utils.types import QFSFinal

def _render_reduce_prompt(query: str, parts: List[Dict[str, Any]], max_ctx_tokens:int) -> str:
    tmpl = Path("graph_based/prompts/qfs_reduce.md").read_text(encoding="utf-8")
    # Concatène les partiels sous forme [id]: texte
    items = []
    for p in parts:
        txt = fit(p["partial"], max_tokens=max_ctx_tokens // max(1, len(parts)))
        items.append(f"[{p['id']} @L{p['level']}] {txt}")
    block = "\n".join(items)
    return tmpl.format(query=query, partials_block=block)

def _parse_json_safe(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"answer": s.strip()[:2000], "used": [], "confidence": 0.5}



def run(series: str, query: str, *, partials: List[Dict[str, Any]], provider, max_reduce_tokens: int = 512) -> QFSFinal: #Dict[str, Any]:
    """
    QFS Reduce: combine les réponses partielles en une réponse globale concise.
    - Output: {"answer","citations":[...], "used_levels":[...], "communities":[...]}

    Agrège les partiels (Map) en une réponse unique.
    INPUT
      - partials: [{"id","level","partial","confidence","evidence"}]
    OUTPUT (AnswerBundle minimal)
      {
        "answer": str,
        "used": [id,...],
        "confidence": float,
        "citations": [{"id":str, "snippet":str}],
        "raw": str
      }
    Convention attendue du LLM (souhaitée, parseur tolérant):
      {"answer":"...", "used":["id1","id2"], "confidence":0.0~1.0}

    """
    prompt = _render_reduce_prompt(query, partials, max_ctx_tokens=max_reduce_tokens)
    raw = provider.ask_llm(prompt)
    js = _parse_json_safe(raw)
    used = [u for u in js.get("used", []) if isinstance(u, str)]
    # citations simples = preuve 1ère phrase de chaque partiel utilisé
    snips = []
    if used:
        by_id = {p["id"]: p for p in partials}
        for uid in used:
            p = by_id.get(uid)
            if p:
                snippet = (p["partial"] or "").split(". ")[0][:280]
                snips.append({"id": uid, "snippet": snippet})
    return {
        "answer": js.get("answer") or js.get("final_answer") or "",
        "used": used,
        "confidence": float(js.get("confidence", 0.6)),
        "citations": snips,
        "raw": raw,
    }