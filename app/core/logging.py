# app/core/logging.py
# JSON logs + request_id safe

from __future__ import annotations
import logging
import logging.config
import contextvars
from typing import Dict, Optional, Any, Callable
from contextlib import contextmanager
import time, uuid, functools, inspect


# Contexte request_id accessible partout
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Filtre pour ajouter le contexte de la requête
class RequestContextFilter(logging.Filter):
    """Ajoute des champs sûrs (request_id, step) pour éviter KeyError."""

    def filter(self, record: logging.LogRecord) -> bool: # type: ignore[override]
        rid = request_id_var.get() or "-"
        # attache les champs même si le formatter les demande
        if not hasattr(record, "request_id"):
            record.request_id = rid
        if not hasattr(record, "step"):
            record.step = "-"
        return True

# Configuration du logging
def setup_logging(level: str = "INFO") -> None:
    # Configuration du format de logging
    # fmt = ("%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s")
    fmt = ("%(asctime)s | %(levelname)s | %(message)s")

    logging.config.dictConfig(
        {
            "version": 1,   # Version du dictionnaire de configuration
            "disable_existing_loggers": False,
            "filters": {
                "request_ctx": {
                    "()": RequestContextFilter,
                }
            },
            "formatters": {
                "std": {"format": fmt},
                "access": {"format": "%(asctime)s | %(levelname)s | %(message)s"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "std",
                    "filters": ["request_ctx"],
                },
                "uvicorn.access": {
                    "class": "logging.StreamHandler",
                    "formatter": "access",
                    "filters": ["request_ctx"],
                },
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
            "loggers": {
                "uvicorn": {"level": level},
                "uvicorn.error": {"level": level},
                "uvicorn.access": {
                    "level": level,
                    "handlers": ["uvicorn.access"],
                    "propagate": False,
                },
            },
        }
    )

# Obtient un logger avec le nom spécifié
def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name)

# Génère un nouvel ID de requête
def new_request_id() -> str:
    return uuid.uuid4().hex