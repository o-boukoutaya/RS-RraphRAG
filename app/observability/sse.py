# app/observability/sse.py
from __future__ import annotations
import asyncio, logging, json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .state import inc_clients, dec_clients, STATUS
from dataclasses import asdict


# File d'attente globale pour pousser les logs vers les clients SSE
LOG_QUEUE: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
STATUS_QUEUE: asyncio.Queue[dict] = asyncio.Queue(maxsize=10)
PIPE_QUEUE: asyncio.Queue[dict] = asyncio.Queue(maxsize=1024)

class SSELogHandler(logging.Handler):
    """Pousse chaque message de log dans la file asyncio (non-bloquant)."""
    def emit(self, record: logging.LogRecord):
        try:
            # ⬇️ Format simple ; si on a déjà du JSON structuré, on serialize record.msg tel quel.
            msg = self.format(record)
            LOG_QUEUE.put_nowait(msg)
        except Exception:
            pass

async def push_status(payload: dict):
    """Appelé par la boucle de santé pour pousser un snapshot."""
    try: await STATUS_QUEUE.put(payload)
    except: pass

async def push_step(event: dict):
    """
    event = {
      "series": "id_de_serie",        # optionnel si tu pilotes par jeu de docs
      "step": "Embedding",            # Ingestion|Embedding|Indexation|GraphBuild|Retrieval
      "phase": "start|end|error",     # état de l'étape
      "ms": 1234,                     # durée si 'end' (optionnel)
      "msg": "info complémentaire"    # optionnel
    }
    """
    try:
        await PIPE_QUEUE.put(event)
    except Exception:
        pass

def attach_sse_log_handler(level=logging.INFO) -> logging.Handler:
    """Attache le handler au root logger."""
    handler = SSELogHandler()
    # format simple; gardez votre format JSON si vous en avez déjà un
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)
    return handler

router = APIRouter(prefix="/api/dev", tags=["dev"])

@router.get("/logs/stream")
async def stream_logs(request: Request):
    """Flux SSE multi-événements : status / log / ping."""
    inc_clients()
    async def event_gen():
      try:
        while True:
            if await request.is_disconnected(): break

            # 1) prioriser status si dispo
            try:
                status = STATUS_QUEUE.get_nowait()
                yield f"event: status\ndata: {json.dumps(status)}\n\n"
            except asyncio.QueueEmpty:
                pass

            # 2) priorité aux steps (non-bloquant)
            try:
                ev = PIPE_QUEUE.get_nowait()
                yield f"event: step\ndata: {json.dumps(ev)}\n\n"
                continue
            except asyncio.QueueEmpty:
                pass

            # 3) puis logs
            try:
                msg = await asyncio.wait_for(LOG_QUEUE.get(), timeout=1.0)
                yield f"event: log\ndata: {json.dumps({'message': msg})}\n\n"
                continue
            except asyncio.TimeoutError:
                # ping keepalive
                yield "event: ping\ndata: {}\n\n"
      finally:
        dec_clients()
    return StreamingResponse(event_gen(), media_type="text/event-stream")

@router.get("/status")
def get_status():
    return asdict(STATUS)