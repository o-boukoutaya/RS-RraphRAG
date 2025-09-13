# tools/graph_rag_tool.py
from __future__ import annotations
from typing import Dict, Any, Optional, Literal
import time

from app.core.resources import get_db, get_provider
from graph_based.kg.summarize import index_search, qfs_map, qfs_reduce
from graph_based.retriever.pathrag import node_retrieval, flow_pruning, prompt_builder
from graph_based.retriever.vector import dense as vector_dense
from graph_based.utils.tokenize import count_tokens

# ---------------- Defaults prudents ----------------

DEFAULT_BUDGETS: Dict[str, Any] = {
    "qfs_map":    {"max_items": 24, "max_prompt_tokens": 900,  "max_response_tokens": 384},
    "qfs_reduce": {"max_items": 12, "max_prompt_tokens": 1200, "max_response_tokens": 384},
    "paths":      {"max_prompt_tokens": 1400, "max_response_tokens": 384},
    "vector":     {"max_prompt_tokens": 1200, "max_response_tokens": 384}
}

# ---------------- MCP: spec ----------------

def mcp_spec() -> Dict[str, Any]:
    """
    Schéma JSON du tool MCP `graph_rag.query`.
    """
    return {
        "name": "graph_rag.query",
        "description": "Router auto GraphRAG / PathRAG / Vector pour répondre avec preuves.",
        "input_schema": {
            "type": "object",
            "properties": {
                "series":  {"type": "string", "description": "Nom de la série (corpus/index)."},
                "query":   {"type": "string", "description": "Question utilisateur."},
                "mode":    {"type": "string", "enum": ["auto", "graph", "path", "vector"], "default": "auto"},
                "budgets": {"type": "object", "description": "Budgets facultatifs par étape (qfs_map/qfs_reduce/paths/vector)."},
                "k":       {"type": "integer", "default": 12, "minimum": 1, "description": "PathRAG/Vector: top-K."},
                "n":       {"type": "integer", "default": 30, "minimum": 5, "description": "PathRAG: top-N nodes."},
                "alpha":   {"type": "number",  "default": 0.8, "minimum": 0.0, "maximum": 1.0, "description": "PathRAG: décroissance."},
                "theta":   {"type": "number",  "default": 0.05, "minimum": 0.0, "maximum": 1.0, "description": "PathRAG: seuil."}
            },
            "required": ["series", "query"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "series": {"type": "string"},
                "mode_used": {"type": "string"},
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "object"}},
                "latency_ms": {"type": "integer"},
                "token_usage": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "integer"},
                        "completion": {"type": "integer"},
                        "total": {"type": "integer"}
                    }
                },
                "debug": {"type": "object"}
            },
            "required": ["series", "mode_used", "question", "answer"]
        }
    }

# ---------------- Router heuristique (auto) ----------------

def _route_auto(question: str) -> Dict[str, Any]:
    """
    Heuristiques légères, déterministes, sans LLM:
    - 'graph' si question ouverte, globale, synthèse, 'compare', 'impact', 'overview', 'tendances', etc.
    - 'path'  si entités/relations explicites, 'comment X est lié à Y', 'entre ... et ...', valeurs numériques/dates,
              'qui/quoi/quand/où' + entités concrètes.
    - 'vector' fallback court/peu structuré.
    """
    q = question.strip().lower()
    long_q = len(q.split()) >= 14
    has_compare = any(w in q for w in ["compare", "différence", "avantages", "inconvénients", "impact", "panorama", "synthèse", "overview"])
    has_graphy = any(w in q for w in ["relation", "lié", "entre", "cause", "conséquence"])
    has_fact = any(q.startswith(w) for w in ["qui", "quoi", "quand", "où", "combien", "lequel", "laquelle"])
    has_dates_nums = any(ch.isdigit() for ch in q)

    if has_compare or (long_q and not has_fact):
        return {"mode": "graph", "rule": "global/sensemaking"}
    if has_graphy or (has_fact and (has_dates_nums or "entre" in q)):
        return {"mode": "path", "rule": "local/fact+relations"}
    return {"mode": "vector", "rule": "fallback/simple"}

# ---------------- Exécutions spécialisées ----------------

def _run_graphrag(*, series: str, question: str, budgets: Dict[str, Any], db, provider) -> Dict[str, Any]:
    t0 = time.perf_counter()

    # 1) Seed search dans l’index (comm-summaries/chunk summaries) — pure lecture
    seeds = index_search.search(series=series, query=question, db=db, provider=provider)  # List[{"text","level","comm_id","score", ...}]
    
    # Quelle la différence entre candidates et seeds ? candidates = seeds ?
    seeds = seeds.get("candidates", []) if isinstance(seeds, dict) else seeds
    
    # 2) QFS map-reduce sur seeds (prompts markdown existants)
    map_out = qfs_map.run(series=series, query=question, candidates=seeds, provider=provider, max_map_tokens=budgets.get("qfs_map", {}).get("max_prompt_tokens", 512))   # List[{"partial","citations":[...]}]
    red_out = qfs_reduce.run(series=series, query=question, partials=map_out.get("partials", []), provider=provider, max_reduce_tokens=budgets.get("qfs_reduce", {}).get("max_prompt_tokens", 512))  # {"answer","citations":[...]}
    
    elapsed = int((time.perf_counter() - t0) * 1000)
    answer = red_out.get("answer", "").strip()
    citations = red_out.get("citations", [])

    # Comptage approximatif
    p_tok = count_tokens("\n".join([s.get("text","") for s in seeds[:12]])) if hasattr(count_tokens, "__call__") else 0
    c_tok = count_tokens(answer) if hasattr(count_tokens, "__call__") else 0

    return {
        "series": series,
        "mode_used": "graph",
        "question": question,
        "answer": answer,
        "citations": citations,
        "latency_ms": elapsed,
        "token_usage": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
        "debug": {"router": {"rule": "graph (global/sensemaking)"}, "seeds": seeds[:24]}
    }

def _run_pathrag(*, series: str, question: str, k: int, n: int, alpha: float, theta: float,
                 budgets: Dict[str, Any], db, provider) -> Dict[str, Any]:
    t0 = time.perf_counter()

    # 1) Node retrieval (top-N entités pertinentes)
    node_res = node_retrieval.topN(series=series, query=question, n=n, db=db)
    # node_res = {"nodes":[{"id","name","type","score"}], "pairs":[(src_id,dst_id), ...]}

    # 2) Path retrieval via flow-pruning (top-K chemins fiables)
    paths = flow_pruning.topK(series=series, nodes=node_res.get("nodes", []), k=k, alpha=alpha, theta=theta, db=db).get("paths", [])
    # paths = flow_pruning.topK(series=series, pairs=node_res["pairs"], k=k, alpha=alpha, theta=theta, db=db)
    # paths = [{"nodes":[...], "edges":[...], "score":float, "ids":{"node_ids":[...],"edge_ids":[...]}}]

    # 3) Prompt path-based (template markdown déjà présent) + génération
    prompt = prompt_builder.build(query=question, paths=paths, max_tokens_for_paths=budgets.get("paths", {}).get("max_prompt_tokens", 1400))
    # prompt = prompt_builder.build(question=question, paths=paths, budgets=budgets.get("paths", {}))
    answer = provider.ask_llm(prompt).strip()

    elapsed = int((time.perf_counter() - t0) * 1000)
    p_tok = count_tokens(prompt) if hasattr(count_tokens, "__call__") else 0
    c_tok = count_tokens(answer) if hasattr(count_tokens, "__call__") else 0

    # Citations = chemins (ids + extraits textuels si disponibles)
    paths.get("ids", {})
    cites = [{"path_score": p.get("score", 0.0), "node_ids": p.get("ids", {}).get("node_ids", []),
              "edge_ids": p.get("ids", {}).get("edge_ids", [])} for p in paths]

    return {
        "series": series,
        "mode_used": "path",
        "question": question,
        "answer": answer,
        "citations": cites,
        "latency_ms": elapsed,
        "token_usage": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
        "debug": {"router": {"rule": "path (fact/relations)"}, "paths": paths}
    }

def _run_vector(*, series: str, question: str, k: int, budgets: Dict[str, Any], db, provider) -> Dict[str, Any]:
    t0 = time.perf_counter()

    chunks = vector_dense.search(series=series, query=question, k=k, db=db, provider=provider)
    # chunks = [{"cid","text","score", "doc","page", ...}]

    # Prompt simple « citations + question »
    head = "Vous êtes un assistant qui répond STRICTEMENT sur la base des extraits fournis.\n"
    head += "Citez explicitement les sources (cid/doc/page). Répondez de façon concise et exacte.\n\n"
    ctx = "\n\n".join([f"[cid={c.get('cid')}] {c.get('text','')}" for c in chunks])
    prompt = head + f"Extraits:\n{ctx}\n\nQuestion: {question}\nRéponse:"

    answer = provider.ask_llm(prompt).strip()
    elapsed = int((time.perf_counter() - t0) * 1000)
    p_tok = count_tokens(prompt) if hasattr(count_tokens, "__call__") else 0
    c_tok = count_tokens(answer) if hasattr(count_tokens, "__call__") else 0

    cites = [{"cid": c.get("cid"), "doc": c.get("doc"), "page": c.get("page"), "score": c.get("score")} for c in chunks]

    return {
        "series": series,
        "mode_used": "vector",
        "question": question,
        "answer": answer,
        "citations": cites,
        "latency_ms": elapsed,
        "token_usage": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
        "debug": {"router": {"rule": "vector (fallback)"}, "chunks": chunks}
    }

# ---------------- Point d’entrée MCP ----------------

def query(series: str, query: str, *, mode: str = "auto",
          budgets: Optional[Dict[str, Any]] = None, k: int = 12, n: int = 30,
          alpha: float = 0.8, theta: float = 0.05,
          db=None, provider=None) -> Dict[str, Any]:
    """
    Point d’entrée MCP:
      - Router (auto):
          if global/sensemaking -> GraphRAG: index_search.search -> qfs_map.run -> qfs_reduce.run
          if local/fact lookup   -> PathRAG : node_retrieval.topN -> flow_pruning.topK -> prompt_builder.build -> provider.ask_llm
          else (fallback)        -> Vector  : vector_dense.search -> prompt (simple) -> provider.ask_llm
      - Retourne AnswerBundle (voir schéma).
    """
    db = db or get_db()
    provider = provider or get_provider()
    budgets = budgets or DEFAULT_BUDGETS

    if mode == "auto":
        r = _route_auto(query)
        mode = r["mode"]

    if mode == "graph":
        return _run_graphrag(series=series, question=query, budgets=budgets, db=db, provider=provider)
    if mode == "path":
        return _run_pathrag(series=series, question=query, k=k, n=n, alpha=alpha, theta=theta,
                            budgets=budgets, db=db, provider=provider)
    # fallback
    return _run_vector(series=series, question=query, k=k, budgets=budgets, db=db, provider=provider)

# (optionnel) petit utilitaire que votre agrégateur importait
def search_data(series: str, query: str, k: int = 8, *, db=None, provider=None) -> Dict[str, Any]:
    """
    Expose un simple 'search' (vector) pour debug/inspection.
    """
    db = db or get_db()
    provider = provider or get_provider()
    chunks = vector_dense.search(series=series, query=query, k=k, db=db, provider=provider)
    return {"series": series, "query": query, "topk": chunks}
