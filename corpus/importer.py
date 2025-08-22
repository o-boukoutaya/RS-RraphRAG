# corpus/importer.py
from __future__ import annotations
from importlib.resources import files
from typing import Iterable, List, Set, Optional
from fastapi import UploadFile
from corpus.models import ImportReport, RejectedFile, Document
from app.core.config import get_settings
from corpus.storage import LocalStorage
from adapters.storage.base import ExtensionNotAllowed, EmptyFile, FileTooLarge  # types d'erreurs
from .utils import sanitize_series, make_series_id
from pathlib import Path
from functools import lru_cache

from app.core.logging import get_logger
logger = get_logger(__name__)

_importer_singleton = None

@lru_cache(maxsize=1)
def get_importer() -> Importer:
    # global _importer_singleton
    # if _importer_singleton is None:
    cfg = get_settings()  # cache déjà géré par get_settings()
    storage = LocalStorage(
        root=cfg.storage.root,
        series_dirname=cfg.storage.series_dirname,
    )
    allowed = {ext.lower() for ext in cfg.storage.allowed_extensions}
    _importer_singleton = Importer(storage=storage, allowed_extensions=allowed)
    return _importer_singleton

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
            # importer : cas “extension interdite”, “fichier vide”, “trop gros” renvoyés proprement sans toucher aux routes.
            except ExtensionNotAllowed as e:
                report.rejected.append(RejectedFile(name=up.filename, reason="extension"))
            except EmptyFile:
                report.rejected.append(RejectedFile(name=up.filename, reason="empty"))
            except FileTooLarge:
                report.rejected.append(RejectedFile(name=up.filename, reason="too_large"))
            except Exception as exc: # pragma: no cover (IO errors)
                report.rejected.append(RejectedFile(name=up.filename, reason=str(exc)))
            

        # logger.info("Importer:import_docs:end", extra={"series": series, "accepted": len(report.accepted), "rejected": len(report.rejected)})
        return report