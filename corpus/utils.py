# corpus/utils.py
from __future__ import annotations
from datetime import datetime
import re, secrets

_SERIES_SAFE = re.compile(r"[^0-9A-Za-z_\-]+", re.UNICODE)

def sanitize_series(value: str | None) -> str | None:
    """Nettoie un nom de série (slug simple). Retourne None si vide."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    value = _SERIES_SAFE.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-_")
    return value or None

def make_series_id(prefix: str = "series") -> str:
    """Ex: series-20250821-194512-a3f2"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rnd = secrets.token_hex(2)  # 4 hex chars
    return f"{prefix}-{ts}-{rnd}"
