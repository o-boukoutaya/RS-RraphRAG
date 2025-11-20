# app/observability/readiness.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ReadinessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, is_ready_flag, exclude_prefixes=("/api/dev", "/docs", "/openapi.json")):
        super().__init__(app)
        self._is_ready = is_ready_flag          # callable qui renvoie bool
        self._exclude = exclude_prefixes

    async def dispatch(self, request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in self._exclude):
            if not self._is_ready():
                return JSONResponse({"detail": "starting"}, status_code=503, headers={"Retry-After": "2"})
        return await call_next(request)
