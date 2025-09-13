# # tools/graph_rag_tool.py
from typing import Dict, Any, List, Tuple
# # from adapters.neo4j_adapter import Neo4jAdapter
# from app.core.resources import get_db, get_provider
# # from adapters.llm.openai_azure import AzureOpenAIProvider
# from graph_based.kg.build.graph_store import GraphStore
# from graph_based.kg.summarize.index_search import pick_condition
# # from graph_based.retriever.pathrag.node_retrieval import topN_nodes
# from graph_based.retriever.pathrag.flow_pruning import k_best_paths, FlowPruner
# from graph_based.retriever.pathrag.node_retrieval import NodeRetriever
# from graph_based.retriever.pathrag.prompt_builder import build_paths_prompt
# from graph_based.prompts.path_prompt import build_path_prompt  # vos prompts existants
# from graph_based.retriever.vector.dense import DenseRetriever
# from graph_based.utils.tokenize import approx_token_count

# # from graph_based.utils.wiring import wire_graph_stack
# from app.core.resources import get_db, get_provider
# from corpus.embedder import Embedder

# # Optionnel: un routeur ultra-simple
# def _route(query: str) -> str:
#     # heuristiques: global sensemaking vs lookup factuel
#     return "pathrag" if len(query) <= 180 and any(t in query.lower() for t in ["qui", "quand", "combien", "quel", "où"]) else "graphrag"


# def graph_query(args: Dict[str, Any]) -> Dict[str, Any]:
#     series = args.get("series", "default")
#     question = args["query"]

#     db, provider, embedder = get_db(), get_provider(), Embedder(provider=get_provider(), db=get_db())
#     mode = _route(question)

#     if mode == "pathrag":
#         nodes = NodeRetriever(series).candidates(question, top_k=40)
#         seeds = [n.get("entity_id") or n.get("cid") for n in nodes[:8] if n]  # à adapter selon votre schéma
#         pruner = FlowPruner(alpha=0.8, theta=0.05)
#         paths = pruner.prune_paths(seeds=seeds, targets=[], k=10)
#         prompt = build_path_prompt(question, paths)   # prompt ordonné par fiabilité croissante
#         answer = provider.ask_llm(prompt)
#         return {"mode": "pathrag", "answer": answer, "evidence": {"paths": paths}}

#     # sinon: GraphRAG global (via résumés C0/C1 déjà pré-calculés dans votre pipeline)
#     # Exemple minimal: récupérer les top communautés (pré-indexées) et faire QFS map/reduce.
#     # Ici, on suppose que vous avez un module summarize.index_search / summarize.comm_summaries
#     from graph_based.kg.summarize.index_search import find_relevant_communities#, search_communities
#     from graph_based.kg.summarize.qfs_map import qfs_map
#     from graph_based.kg.summarize.qfs_reduce import qfs_reduce

#     # comms = search_communities(db=db, query=question, limit=12)  # votre index de C0/C1
#     comms = find_relevant_communities(db=db, query=question, level="C0")
#     partials = [qfs_map(question, c["summary"]) for c in comms]
#     answer = qfs_reduce(question, partials)
#     return {"mode": "graphrag", "answer": answer, "evidence": {"communities": [c["id"] for c in comms]}}




# # ---- wiring minimal (à injecter depuis votre app) ----
# GS: GraphStore = None         # set at startup
# NODE_INDEX: DenseRetriever = None # idem
# ID2TEXT: Dict[str,str] = {}   # id -> text/name
# NODE_TRUST: Dict[str,float] = {}  # id -> trust score (deg/quality)

# def init_graph_tool(neo4j_driver=None, memory=False, id2text=None, node_trust=None):
#     global GS, NODE_INDEX, ID2TEXT, NODE_TRUST
#     GS = GraphStore("memory" if memory else "neo4j", Neo4jAdapter(neo4j_driver) if not memory else None)
#     ID2TEXT = id2text or {}
#     NODE_TRUST = node_trust or {i:1.0 for i in ID2TEXT}
#     # Build dense index once
#     NODE_INDEX = DenseIndex.build(list(ID2TEXT.keys()), [ID2TEXT[i] for i in ID2TEXT])

# # ---- MCP-facing tools ----

# def tool_graph_query(query: str, mode: str = "auto", N: int = 40, K: int = 15,
#                      alpha: float = 0.8, theta: float = 0.05, max_hops: int = 4) -> Dict[str, Any]:
#     """
#     mode: 'sensemake' -> GraphRAG (C0..), 'lookup' -> PathRAG, 'auto' -> routeur.
#     Pour la démo, on implémente le chemin PathRAG (lookup). Sensemaking dépend de vos résumés C0..C3.
#     """
#     # routeur trivial
#     if mode == "auto":
#         cond = pick_condition(query)
#         mode = "sensemake" if cond == "C0" else "lookup"

#     if mode == "lookup":
#         # 1) top-N nodes
#         top_nodes = topN_nodes(NODE_INDEX, ID2TEXT, query, N=N)
#         seeds = [i for i,_ in top_nodes]
#         # 2) K paths with pruning
#         def neighbors(u): 
#             return list(GS.neighbors(u))
#         def edge_lu(u,v):
#             # première arête u->v
#             for _v, et, props in GS.neighbors(u):
#                 if _v == v: return et, (props.get("description") or "")
#             return "RELATED",""
#         paths = k_best_paths(neighbors, seeds, NODE_TRUST, K=K, alpha=alpha, theta=theta, max_hops=max_hops)
#         prompt = build_paths_prompt(query, paths, edge_lu)
#         # LLM generation: utilisez votre pipeline existant
#         # answer = your_llm.generate(PATH_PROMPT_TMPL.format(...))
#         tokens = approx_token_count(prompt)
#         return {"mode":"PathRAG","seeds":seeds[:10],"paths_used":len(paths),"prompt_preview":prompt[:1200],
#                 "est_ctx_tokens": tokens}

#     # Sensemaking -> à brancher avec vos résumés C0..C3 + prompts qfs_map/reduce
#     return {"mode":"GraphRAG","todo":"brancher vos résumés communautaires C0..C3 puis map/reduce"}


def mcp_spec() -> Dict[str, Any]:
    """
    Déclare le tool 'graph_rag.query' (schéma JSON des args/sortie).
    """
    return {"name": "graph_rag.query", "args": {"query": "str", "mode": "str"}, "output": "dict"}



def query(series: str, query: str, *, mode: str = "auto", budgets: Dict[str, Any] | None = None, k: int = 12, n: int = 30, alpha: float = 0.8, theta: float = 0.05, db=None, provider=None) -> Dict[str, Any]:
    """
    Point d’entrée MCP:
      - Router (auto):
          if global/sensemaking -> GraphRAG: index_search.search -> qfs_map.run -> qfs_reduce.run
          if local/fact lookup   -> PathRAG : node_retrieval.topN -> flow_pruning.topK -> prompt_builder.build -> provider.ask_llm
          else (fallback)        -> vector.search -> prompt_builder (simple) -> provider.ask_llm
      - Retourne AnswerBundle (cf. Entrée B).
    """
    return {"mode": "todo", "answer": "implémenter votre pipeline ici selon vos besoins spécifiques."}
