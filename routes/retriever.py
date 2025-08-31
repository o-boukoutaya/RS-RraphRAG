from __future__ import annotations
from fastapi import APIRouter, Body, UploadFile, File, Form
from app.core.resources import get_provider
from corpus.embedder import Embedder
from adapters.db.neo4j import Neo4jAdapter

from corpus.retriever.schemas import SearchRequest, SearchResponse
from tools.graph_rag_tool import kg_ret, dn_ret, hy_ret

router = APIRouter(prefix="/retriever", tags=["retriever"])


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    if req.mode == "kg":    return kg_ret.search(req)
    if req.mode == "dense": return dn_ret.search(req)
    return hy_ret.search(req)
