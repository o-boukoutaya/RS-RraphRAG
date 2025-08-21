# routes/corpus.py
from fastapi import APIRouter, UploadFile, File
from app.core.config import get_settings
from adapters.storage.local import LocalStorage
from corpus.importer import ImporterService

router = APIRouter(prefix="/api/v2/corpus", tags=["corpus"])
_settings = get_settings()
_storage = LocalStorage(_settings.storage.root_dir, _settings.storage.tmp_dir)
_importer = ImporterService(_storage, _settings.storage.allowed_extensions)

@router.post("/series/{series}/import")
async def import_files(series: str, files: list[UploadFile] = File(...)):
    payload = [(f.filename, await f.read()) for f in files]
    docs = _importer.import_bytes(series, payload)
    return {"count": len(docs), "files": [d.filename for d in docs]}
