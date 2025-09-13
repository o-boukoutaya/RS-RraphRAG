# graph_based/retriever/pathrag/prompt_builder.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from pathlib import Path
from graph_based.utils.tokenize import fit
from graph_based.utils.types import PathRef

def render_path_text(path: List[str], edges_lookup) -> str:
    """
    edges_lookup(u,v) -> (etype, desc_str)
    """
    parts = []
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        et, desc = edges_lookup(u, v)
        parts.append(f"<{u}> --({et}:{desc})-> <{v}>")
    return " ; ".join(parts)

def build_paths_prompt(question: str, paths: List[Tuple[List[str], float]], edges_lookup) -> str:
    # PathRAG: ordre croissant de fiabilité (mitige lost-in-the-middle)
    paths_sorted = sorted(paths, key=lambda x: x[1])  # ascending
    path_texts = [render_path_text(p, edges_lookup) for p,_ in paths_sorted]
    numbered = "\n".join(f"({i+1}) {t}" for i,t in enumerate(path_texts))
    return f"Question: {question}\n\nPath information:\n{numbered}\n"

def _render_paths_block(paths: List[Dict[str, Any]], max_tokens:int) -> str:
    """
    Encode chaque chemin sous forme lisible <u> --[pred]--> <v> (+ descriptions si disponibles).
    Les chemins sont déjà triés par score (fiabilité). On renvoie du moins fiable au plus fiable.
    """
    lines = []
    share = max_tokens // max(1, len(paths))
    for p in paths:
        parts = []
        nodes = p.get("nodes", [])
        edges = p.get("edges", [])
        for i in range(len(edges)):
            u = nodes[i]; v = nodes[i+1]; e = edges[i]
            u_desc = fit(u.get("name",""), max_tokens=share//8)
            v_desc = fit(v.get("name",""), max_tokens=share//8)
            pred = e.get("pred","relates_to")
            parts.append(f"<{u_desc}> --[{pred}]--> <{v_desc}>")
        if parts:
            lines.append(" • " + " ; ".join(parts))
    return "\n".join(lines)


def build(query: str, paths: List[PathRef], *, max_tokens_for_paths: int = 800) -> str:
    """
    Construit le prompt 'path-based' (gabarit PathRAG) ordonné par fiabilité croissante.
    - Output: {"messages":[...]} ou {"prompt": "..."} selon votre provider.
    - Contient des balises/citations pour tracer chaque affirmation aux IDs de chemins/nœuds/chunks.

    Construit le prompt final PathRAG.
    INPUT
      - query: question utilisateur
      - paths: [{nodes:[{name...}], edges:[{pred...}], score:float}, ...]
               ATTENTION: fournir paths triés par score croissant ici
    OUTPUT
      - prompt (str) à envoyer dans provider.ask_llm(prompt)
    """
    # Tri: moins fiable -> plus fiable (le plus fiable en fin de prompt)
    paths_sorted = sorted(paths, key=lambda x: float(x.get("score",0.0)))
    paths_block = _render_paths_block(paths_sorted, max_tokens=max_tokens_for_paths)
    tmpl = Path("graph_based/prompts/path_prompt.md").read_text(encoding="utf-8")
    return tmpl.format(question=query, paths_block=paths_block)