# app/core/logging.py
# JSON logs + request_id safe
# Core/logging : JSON, request_id forcé par Filter, logs Uvicorn harmonisés (terminal + retours API).

import json, logging, sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get("-")
        return True

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "module": record.module,
            "func": record.funcName,
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging(level="INFO"):
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]

    # Harmoniser Uvicorn
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        lg = logging.getLogger(name)
        lg.setLevel(level)
        for h in lg.handlers:
            h.addFilter(RequestIdFilter())


# Le filter garantit qu’on n’aura plus l’erreur “Formatting field not found: request_id” même pour les logs d’Uvicorn.