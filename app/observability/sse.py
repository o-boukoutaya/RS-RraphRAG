# app/observability/sse.py
import asyncio
import logging
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

# File d'attente globale pour pousser les logs vers les clients SSE
LOG_QUEUE: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)

class SSELogHandler(logging.Handler):
    """Pousse chaque message de log dans la file asyncio (non-bloquant)."""
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            LOG_QUEUE.put_nowait(msg)
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
    """Diffuse les logs en temps réel via Server-Sent Events (SSE)."""
    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await LOG_QUEUE.get()
                # Encapsule en événement SSE
                yield f"data: {json.dumps({'message': msg})}\n\n"
            except asyncio.CancelledError:
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")
