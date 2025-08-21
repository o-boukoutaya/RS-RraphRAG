# app/core/middleware.py
import time, uuid, logging
from starlette.middleware.base import BaseHTTPMiddleware
from .logging import request_id_var

log = logging.getLogger("app.middleware")

# Middleware : RequestContextMiddleware pose X-Request-ID/UUID et mesure la latence.
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(rid)
        start = time.perf_counter()
        log.info("request.start", extra={"path": request.url.path, "method": request.method})
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start)*1000, 2)
            log.info("request.end", extra={"path": request.url.path, "duration_ms": duration_ms})
            request_id_var.reset(token)
