# app/core/middleware.py
from __future__ import annotations
import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .logging import request_id_var, get_logger, new_request_id

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injecte un request_id + logs start/stop + durée."""

    def __init__(self, app, header_name: str = "X-Request-Id") -> None: # type: ignore[no-untyped-def]
        super().__init__(app)
        self.header_name = header_name
        self.log = get_logger(__name__)

    async def dispatch(self, request: Request, call_next: Callable): # type: ignore[override]
        rid = request.headers.get(self.header_name) or new_request_id()
        token = request_id_var.set(rid)
        start = time.perf_counter()
        self.log.info("request start %s %s", request.method, request.url.path)
        try:
            response: Response = await call_next(request)
        finally:
            duration = (time.perf_counter() - start) * 1000
            self.log.info("request end %s %s (%.2f ms)", request.method, request.url.path, duration)
            request_id_var.reset(token)
        response.headers[self.header_name] = rid
        return response