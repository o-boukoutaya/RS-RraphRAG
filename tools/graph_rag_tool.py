from __future__ import annotations
from typing import Literal
from fastmcp import FastMCP
from corpus.retriever.schemas import SearchRequest, SearchResponse
from corpus.retriever.kg import KGRetriever
from corpus.retriever.dense import DenseRetriever
from corpus.retriever.hybrid import HybridRetriever
from adapters.db.neo4j import client_from_settings
from app.core.resources import get_db

from adapters.db.neo4j import Neo4jAdapter
from adapters.llm.openai_azure import AzureOpenAIProvider  # ou GeminiProvider selon provider
from app.core.resources import get_provider
# from corpus.kg.runner import retriever_query   # ta logique existante



mcp = FastMCP(title="GraphRAG MCP")

# Pré-instanciation (singleton)
_db = client_from_settings()
kg_ret = KGRetriever(_db)
dn_ret = DenseRetriever(_db)
hy_ret = HybridRetriever(kg_ret, dn_ret)


@mcp.tool()
async def default_tool(word: str) -> str:
    """Un outil de test simple."""
    return f"Tools are ready! Result for: {word}!"

@mcp.tool()
async def db_ping() -> bool:
    """ Tester la connexion avec Neo4J """
    from app.core.resources import test_cnx
    return test_cnx()

@mcp.tool()
async def search_data(
    query: str,
    mode: str = "hybrid",
    k: int = 6,
    series: str | None = None,
    filters: dict | None = None,
    index_name: str | None = None,
    pipeline: Literal["anchors","anchors+expand","full"]= "anchors"
) -> dict:
    """
    Recherche dans le KG / l'index vectoriel ou hybride.
    Retourne un JSON prêt pour le LLM (hits + diagnostiques).
    anchors         -> renvoie seulement les 'hits' (retour actuel)
    anchors+expand  -> ajoute 'neighbors' (les projets reliés)
    full            -> ajoute 'evidence' (chunks) prêts pour la synthèse
    """
    req = SearchRequest(query=query, mode=mode, k=k, series=series, filters=filters or {}, index_name=index_name, pipeline=pipeline)
    if req.mode == "kg":
        res: SearchResponse = kg_ret.search(req)
    elif req.mode == "dense":
        res = dn_ret.search(req)
    else:
        res = hy_ret.search(req)
    return res.model_dump()



# @mcp.tool()
# async def rag_search(
#     query: str,
#     mode: Literal["kg", "vec", "hybrid"] = "hybrid",
#     k: int = 8,
#     series: Optional[str] = None
# ) -> dict:
#     """Recherche dans le graphe/index. Retourne hits + cypher/params si mode=kg."""
#     # appelle ton retriever existant et retourne un JSON structuré (déjà en place chez toi)
#     return await retriever_query(query=query, mode=mode, k=k, series=series)

# @mcp.tool()
# async def rag_cypher(nl_query: str, series: Optional[str] = None, k: int = 50) -> dict:
#     """Traduction NL→Cypher via LLM puis exécution sur Neo4j (résultats tabulaires)."""
#     provider = get_provider()
#     # 1) générer un Cypher sûr (prompt NL2Cypher)
#     cypher, params = await provider.nl2cypher(nl_query, series=series, k=k)
#     # 2) exécuter
#     db = Neo4jAdapter()
#     rows = db.run_tabular(cypher, params or {})
#     return {"cypher": cypher, "params": params, "rows": rows}

# # (optionnel)
# @mcp.tool()
# async def rag_answer(question: str, series: Optional[str] = None, k: int = 6, mode: str = "hybrid") -> dict:
#     """Recherche + génération d'une réponse 'finale' citée (chunks & entités)."""
#     provider = get_provider()
#     ret = await retriever_query(query=question, mode=mode, k=k, series=series)
#     context = provider.render_context(ret)         # assemble les passages
#     answer  = await provider.answer_with_citations(question, context)  # prompt structuré
#     return {"answer": answer, "evidence": ret}