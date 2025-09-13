from importlib.resources import files
from fastapi import APIRouter, Body, UploadFile, File, Form
from app.core.resources import get_provider, get_db
from app.core.logging import get_logger
from graph_based.utils.types import BuildReport


router = APIRouter(prefix="/pipelines", tags=["pipelines"])
logger = get_logger(__name__)

@router.get("/") # get http://localhost:8000/api/pipelines/
async def list_pipelines():
    return {"pipelines": []}

@router.post("/graph/build")
async def build_graph_pipeline(series: str, options: dict) -> BuildReport:
    from pipelines.build_graph import run as build_run
    return build_run(series=series, options=options, db=get_db(), provider=get_provider())

@router.get("/list_chunks") # get http://localhost:8000/api/pipelines/list_chunks?serie=cat-2025-Q1
async def list_chunks(serie: str):
    db = get_db()
    chunks = db.stream_chunks(serie)
    return {"serie": serie, "chunks": chunks}