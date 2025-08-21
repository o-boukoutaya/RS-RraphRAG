# corpus/importer.py
from __future__ import annotations
from importlib.resources import files
from typing import Iterable, List, Set, Optional
from fastapi import UploadFile
from .models import ImportReport, RejectedFile, Document
from .storage import LocalStorage
from .utils import sanitize_series, make_series_id
from pathlib import Path

from app.core.logging import get_logger
logger = get_logger(__name__)

class Importer:
    """Service métier : gère l'import multi-fichiers et les règles d'acceptation."""

    def __init__(self, storage: LocalStorage, allowed_extensions: Iterable[str]) -> None:
        self.storage = storage
        self.allowed: Set[str] = {ext.lower().strip() for ext in (allowed_extensions or {
            ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".xls"
        })}

    def _is_allowed(self, filename: str) -> bool:
        dot = filename.rfind('.')
        ext = filename[dot:].lower() if dot != -1 else ''
        return ext in self.allowed

    async def import_files(self, *, series: Optional[str], uploads: List[UploadFile]) -> ImportReport:
        # logger.info("Importer:import_docs:start", extra={"series": series, "count": len(uploads)})

        series = sanitize_series(series) or make_series_id()
        
        report = ImportReport(series=series)
        for up in uploads:
            if not up.filename:
                report.rejected.append(RejectedFile(filename="<empty>", reason="missing filename"))
                continue
            if not self._is_allowed(up.filename):
                report.rejected.append(RejectedFile(filename=up.filename, reason="extension not allowed"))
                continue
            try:
                doc = await self.storage.save_upload(series, up)
                report.accepted.append(doc)
            except Exception as exc: # pragma: no cover (IO errors)
                report.rejected.append(RejectedFile(filename=up.filename, reason=str(exc)))

        # logger.info("Importer:import_docs:end", extra={"series": series, "accepted": len(report.accepted), "rejected": len(report.rejected)})
        return report