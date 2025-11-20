# app/main.py
from app.core.logging import setup_logging, get_logger
setup_logging("INFO")

from app.core.middleware import RequestContextMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.observability.sse import router as dev_router, attach_sse_log_handler, push_status,SSELogHandler
from app.observability.state import Phase, STATUS, health_loop
from app.observability.readiness import ReadinessMiddleware

from dataclasses import asdict

from routes import api_router
from contextlib import asynccontextmanager, suppress
import asyncio, logging
from app.core.config import get_settings

from tools.mcp_tools import mcp as mcp_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- START-UP ---
    STATUS.phase = Phase.STARTING
    app.state.ready = False
    await push_status(asdict(STATUS))            # <-- impulsion immédiate

    # Attacher le handler SSE aux logs
    handler = attach_sse_log_handler()
    # app.state.sse_log_handler = handler

    # Lancer la boucle santé
    app.state.health_task = asyncio.create_task(health_loop())

    transport = get_settings().app.transport
    if transport == "stdio":
        # Optional: run stdio transport in background (not used when mounting SSE app)
        app.state.mcp_task = asyncio.create_task(mcp_app.run_stdio_async())
    STATUS.phase = Phase.RUNNING
    app.state.ready = True
    await push_status(asdict(STATUS))            # <-- impulsion immédiate
    
    try:
        yield  # —— l’application tourne ici ——
    finally:
        # --- SHUTDOWN ---
        STATUS.phase = Phase.STOPPING
        app.state.ready = False
        await push_status(asdict(STATUS))

        if transport in {"sse", "stdio"} or getattr(app.state, "mcp_task", None):
            app.state.mcp_task.cancel()
            with suppress(asyncio.CancelledError):
                await app.state.mcp_task
        
        health = getattr(app.state, "health_task", None)
        if health:
            health.cancel()
            with suppress(asyncio.CancelledError):
                await health
        STATUS.phase = Phase.STOPPED
        await push_status(asdict(STATUS))

sub_app = mcp_app.sse_app()

app = FastAPI(
    title="graphrag",
    lifespan=lifespan
    # lifespan=sub_app.router.lifespan_context,
)
app.add_middleware(
    ReadinessMiddleware, 
    is_ready_flag=lambda: getattr(app.state, "ready", False))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:5173", "http://127.0.0.1:5173", "*" ],  # à restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attacher le handler SSE AU DÉMARRAGE
attach_sse_log_handler()

app.mount("/mcp-server", sub_app) #, "mcp")

app.add_middleware(RequestContextMiddleware)
app.include_router(dev_router)
app.include_router(api_router)

log = get_logger(__name__)
log.info("App ready.")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host=get_settings().app.host, port=get_settings().app.port, reload=True)
#     log.info("App ready.")




















# http://127.0.0.1:8050/docs#/
# uvicorn app.main:app --reload --port 8050
# uvicorn app.main:app --reload --port 8050 --log-level debug <- Lance avec logs verbeux
