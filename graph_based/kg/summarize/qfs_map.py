# graph_based/kg/summarize/qfs_map.py
from __future__ import annotations
from typing import List, Dict, Any
import json, re
from pathlib import Path
from graph_based.utils.tokenize import fit
from graph_based.utils.types import QFSMapOut

def _render_map_prompt(query: str, summary: str) -> str:
    # Charge le prompt Markdown et injecte {query} / {summary}
    tmpl = Path("graph_based/prompts/qfs_map.md").read_text(encoding="utf-8")
    return tmpl.format(query=query, summary=summary)


def _parse_json_safe(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)  # premier bloc JSON
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    # fallback minimal
    return {"partial_answer": s.strip()[:2000], "confidence": 0.4, "evidence": []}

def run(series: str, query: str, *, candidates: List[Dict[str, Any]], provider, max_map_tokens: int = 512,) -> QFSMapOut: # Dict[str, Any]
    """
    QFS Map: calcule des réponses partielles par communauté (en parallèle).
    - Output: [{"community_id","partial_answer","score","citations":[...]}...]
    - Appelé par: tool (mode global) → reduce

    Exécute QFS-Map: un appel LLM par résumé.
    INPUTS
      - series, query
      - candidates: [{id, level, text, score}]
      - provider: .ask_llm(prompt:str)->str
    OUTPUT
      {
        "partials": [
          {"id": str, "level": int, "partial": str, "confidence": float, "evidence": [str]}
        ]
      }
    Convention de sortie attendue du LLM (souhaitée, mais parseur tolérant):
      {"partial_answer": "...", "confidence": 0.0~1.0, "evidence": ["...","..."]}
    """
    partials: List[Dict[str, Any]] = []
    for c in candidates:
        prompt = _render_map_prompt(query, fit(c["text"], max_tokens=max_map_tokens))
        raw = provider.ask_llm(prompt)
        js = _parse_json_safe(raw)
        partials.append({
            "id": c["id"],
            "level": int(c["level"]),
            "partial": js.get("partial_answer") or js.get("answer") or js.get("output") or "",
            "confidence": float(js.get("confidence", 0.5)),
            "evidence": list(js.get("evidence", [])),
        })
    return {"partials": partials}