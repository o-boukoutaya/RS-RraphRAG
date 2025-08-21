# routes/corpus.py
from fastapi import APIRouter, UploadFile, File, Form
from typing import List, Annotated, Optional
from functools import lru_cache
from app.core.logging import get_logger
from app.core.config import get_settings
from corpus.importer import Importer
from corpus.storage import LocalStorage
# from app.core.logging import step

# router = APIRouter(prefix="/api/v2/corpus", tags=["corpus"])
router = APIRouter(prefix="/corpus", tags=["corpus"])
logger = get_logger(__name__)

@lru_cache(maxsize=1)
def get_importer() -> Importer:
    cfg = get_settings()  # cache déjà géré par get_settings()
    storage = LocalStorage(
        root=cfg.storage.root,
        series_dirname=cfg.storage.series_dirname,
    )
    allowed = {ext.lower() for ext in cfg.storage.allowed_extensions}
    return Importer(storage=storage, allowed_extensions=allowed)

def _import_extra(*, series=None, files=None, **_):
    return {"series": series, "count": len(files or [])}

@router.post("/import")
async def import_docs(
    series: Annotated[Optional[str], Form()] = None,                 # <- optionnel
    files: Annotated[List[UploadFile], File(...)] = ...
):
    logger.info("POST:import_docs:start", extra={"series": series, "count": len(files)})
    report = await get_importer().import_files(series=series, uploads=files)
    logger.info("import_docs:end", extra={"series": series, "accepted": len(report.accepted), "rejected": len(report.rejected)})
    return report