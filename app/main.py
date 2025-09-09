# app/main.py
from app.core.logging import setup_logging, get_logger
setup_logging("INFO")

from app.core.middleware import RequestContextMiddleware
from fastapi import FastAPI
from routes import api_router
from contextlib import asynccontextmanager
import contextlib, asyncio
from app.core.config import get_settings

from tools.graph_rag_tool import mcp as mcp_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = get_settings().app.transport
    # START-UP
    if transport == "stdio":
        # Optional: run stdio transport in background (not used when mounting SSE app)
        app.state.mcp_task = asyncio.create_task(mcp_app.run_stdio_async())
    # For SSE, we'll mount the Starlette sub-app instead of spawning a separate server.

    yield  # —— l’application tourne ——

    # SHUT-DOWN
    if transport in {"sse", "stdio"}:
        app.state.mcp_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.mcp_task

sub_app = mcp_app.sse_app()

app = FastAPI(
    title="graphrag",
    lifespan=lifespan
    # lifespan=sub_app.router.lifespan_context,
)

app.mount("/mcp-server", sub_app) #, "mcp")

# app.add_middleware(RequestContextMiddleware)
app.include_router(api_router)

log = get_logger(__name__)
log.info("App ready.")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host=get_settings().app.host, port=get_settings().app.port, reload=True)
#     log.info("App ready.")




# =============================================================================
# # app/main.py
# from app.core.logging import setup_logging, get_logger
# setup_logging("INFO")

# from app.core.middleware import RequestContextMiddleware
# from fastapi import FastAPI
# from routes import api_router

# from tools.graph_rag_tool import mcp as mcp_app
# # from tools.rag_tool import build_server
# # Sous-app SSE pour MCP (même event loop → latence minimale)

# # mcp_app = build_server(port=8050)

# sub_app = mcp_app.sse_app()


# app = FastAPI(
#     title="graphrag",
#     lifespan=sub_app.router.lifespan_context,  # réutilise le lifespan SSE
# )

# app.mount("/mcp-server", sub_app, "mcp")

# # app.add_middleware(RequestContextMiddleware)
# app.include_router(api_router)

# log = get_logger(__name__)

# log.info("App ready.")
# =============================================================================























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