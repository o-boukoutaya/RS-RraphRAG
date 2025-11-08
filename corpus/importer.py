# corpus/importer.py
from __future__ import annotations
from importlib.resources import files
from typing import Iterable, List, Set, Optional
from fastapi import UploadFile
from corpus.models import ImportReport, RejectedFile, Document
from app.core.config import get_settings
from app.core.resources import get_storage
# from corpus.storage import LocalStorage
# from adapters.storage.local import LocalStorage
from app.core.resources import get_storage
from adapters.storage.base import ExtensionNotAllowed, EmptyFile, FileTooLarge  # types d'erreurs
from .utils import sanitize_series, make_series_id
from pathlib import Path
# from functools import lru_cache

from app.core.logging import get_logger
logger = get_logger(__name__)

# _importer_singleton = None

# @lru_cache(maxsize=1)
# def get_importer() -> Importer:
#     # global _importer_singleton
#     # if _importer_singleton is None:
#     cfg = get_settings()  # cache déjà géré par get_settings()
#     storage = LocalStorage(
#         root=cfg.storage.root,
#         series_dirname=cfg.storage.series_dirname,
#     )
#     allowed = {ext.lower() for ext in cfg.storage.allowed_extensions}
#     _importer_singleton = Importer(storage=storage, allowed_extensions=allowed)
#     # endif
#     return _importer_singleton

class Importer:
    """Service métier : gère l'import multi-fichiers et les règles d'acceptation."""

    def __init__(self) -> None:
        # self.storage = LocalStorage()
        self.storage = get_storage()
        self.allowed = self.storage.allowed

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
                report.rejected.append(RejectedFile(filename=up.filename, reason="extension"))
            except EmptyFile:
                report.rejected.append(RejectedFile(filename=up.filename, reason="empty"))
            except FileTooLarge:
                report.rejected.append(RejectedFile(filename=up.filename, reason="too_large"))
            except Exception as exc: # pragma: no cover (IO errors)
                reason = getattr(exc, "__class__", type("E",(object,),{})).__name__
                report.rejected.append(RejectedFile(filename=up.filename, reason=reason, message=str(exc)))
            
        # logger.info("Importer:import_docs:end", extra={"series": series, "accepted": len(report.accepted), "rejected": len(report.rejected)})
        return report
    
    # Méthodes qui retourne toutes les fichiers importés sous une séries(sous data/) -> [{id,name,size,created}]  
    def get_series_files(self, serie_name: str):
        return self.storage.list_series_imported_files(serie_name=serie_name)
    
    def serie_meta(self, serie_name: str):
        meta = self.storage.get_series_metadata(serie_name=serie_name)
        return meta
        # return { "files":{meta.get("files", 0)}, "chunks":{meta.get("chunks", 0)}, "embeddings":{meta.get("embeddings", 0)}, "graph":{meta.get("graph", 0)}, "communities":{meta.get("communities", 0)}, "reports":[...] }