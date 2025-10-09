from __future__ import annotations
import time
from typing import Literal, Dict, Any, Optional

# -- Core Server --------
from app.core.resources import get_db, get_mcp, get_provider
mcp = get_mcp()

# -- Tools Logic --------
from app.core.resources import test_cnx
from tools.graphrag import mcp_spec, query as graph_query
from tools.graph_rag_tool import search_data



# -- Expose default Tools -------
@mcp.tool()
async def default_tool(word: str) -> str:
    """Un outil de test simple."""
    return f"Tools are ready! Result for: {word}!"

@mcp.tool()
async def db_ping() -> bool:
    """ Tester la connexion avec Neo4J """
    
    return test_cnx()


# -- GraphRAG (based) Tool ------

@mcp.tool()
async def graph_rag_query() -> Dict[str, Any]:
    return mcp_spec()

@mcp.tool()
async def search(series: str, query: str, *, mode: str = "auto",
                     budgets: Dict[str, Any] | None = None,
                     k: int = 12, n: int = 30, alpha: float = 0.8, theta: float = 0.05) -> Dict[str, Any]:
    """
    Point d’entrée MCP:
      - Router (auto):
          if global/sensemaking -> GraphRAG: index_search.search -> qfs_map.run -> qfs_reduce.run
          if local/fact lookup   -> PathRAG : node_retrieval.topN -> flow_pruning.topK -> prompt_builder.build -> provider.ask_llm
          else (fallback)        -> Vector  : vector_dense.search -> prompt (simple) -> provider.ask_llm
      - Retourne AnswerBundle (voir schéma).
    """
    # Object of type str is not callable ? : 'str' object is not callable, what to do ? : vérifier les types, ajouter des assertions, etc.
    # Attribute "__call__" is unknown ? : Object of type 'str' has no '__call__' member, what to do ? : vérifier les types, ajouter des assertions, etc.
    return graph_query(series=series, query=query, mode=mode, budgets=budgets, k=k, n=n, alpha=alpha, theta=theta, db=get_db(), provider=get_provider())


# -- Old KG Retriever Tool ------

@mcp.tool()
async def kg_retriever_query(query: str) -> Dict[str, Any]:
    """Interroger le KG avec une requête."""
    return await search_data(query=query, mode="kg")