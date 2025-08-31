# app/main.py
from app.core.logging import setup_logging, get_logger
setup_logging("INFO")

from app.core.middleware import RequestContextMiddleware
from fastapi import FastAPI
from routes import api_router

from tools.graph_rag_tool import mcp as mcp_app
# Sous-app SSE pour MCP (même event loop → latence minimale)
sub_app = mcp_app.sse_app()


app = FastAPI(
    title="GraphRAG Admin + MCP",
    lifespan=sub_app.router.lifespan_context,  # réutilise le lifespan SSE
)

app.mount("/mcp-server", sub_app, "mcp")

app.add_middleware(RequestContextMiddleware)
app.include_router(api_router)

log = get_logger(__name__)

log.info("App ready.")




# http://127.0.0.1:8050/docs#/
# uvicorn app.main:app --reload --port 8050
# uvicorn app.main:app --reload --port 8050 --log-level debug <- Lance avec logs verbeux


# neptune
# build graph:
# - use just LLM with prompt
# - define classes for graph nodes and relations (as tools) and use the LLM prompt to create them
# - use LLMGraphTransformer from langchain to transform row text into graph nodes and relations

# from typing import List, Optional
# class Node(BaseNode):
#     id: str
#     labels: str
#     properties: Optional[List[Property]]

# class Relationship(BaseRelationship):
#     id: str
#     source: str
#     target: str
#     type: str
#     properties: Optional[List[Property]]

# class KnowledgeGraph(BaseModel):
#     """Generate a knowledge graph with entities and relationships."""
#     nodes: List[Node] = Field(
#         ..., description="List of nodes in the knowledge graph"
#     )
#     rels: List[Relationship] = Field(
#         ..., description="List of relationships in the knowledge graph"
#     )