from fastapi import APIRouter, Body
from app.core.resources import get_provider
from corpus.embedder import Embedder
from adapters.db.neo4j import Neo4jAdapter

from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

@router.get("/")
async def list_pipelines():
    return {"pipelines": []}

