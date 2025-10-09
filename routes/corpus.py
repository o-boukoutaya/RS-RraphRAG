# routes/corpus.py
from fastapi import APIRouter, HTTPException, UploadFile, BackgroundTasks, File, Form, Query, Body
from typing import List, Annotated, Optional, Set, Literal

from pydantic import BaseModel
from adapters.db.neo4j import Neo4jAdapter
from app.core.logging import get_logger
from app.core.resources import get_all_series, get_provider, get_db

from corpus.importer import Importer
from corpus.extractor.engine import ExtractorRunner
from corpus.extractor.base import ExtractOptions, options_from_request, _parse_ranges
from corpus.chunker import ChunkRunner, ChunkOptions
from corpus.kg.runner import KGRunner
from corpus.models import ExtractRequest, KGBuildRequest
from corpus.embedder import Embedder

from fastapi import APIRouter, Body
from app.core.resources import get_provider




# router = APIRouter(prefix="/api/v2/corpus", tags=["corpus"])
router = APIRouter(prefix="/corpus", tags=["corpus"])
logger = get_logger(__name__)

@router.post("/import")
async def import_docs(
    series: Annotated[Optional[str], Form()] = None, # <- optionnel
    files: Annotated[List[UploadFile], File(...)] = []
):
    # return {"test": "test"}
    logger.info("POST:import_docs:start", extra={"series": series, "count": len(files)})
    report = await Importer().import_files(series=series, uploads=files)
    logger.info("import_docs:end", extra={"series": series, "accepted": len(report.accepted), "rejected": len(report.rejected)})
    return report

@router.get("/series")
async def get_series():
    return {"series": get_all_series()}


@router.post("/extract-serie")
async def extract_serie(req: ExtractRequest, background: BackgroundTasks):
    # Validation minimale côté route (laisse Pydantic faire le reste)
    if not req.series:
        # 422 standard FastAPI si champ manquant
        raise HTTPException(status_code=422, detail=[{
            "loc": ["body", "series"], "msg": "Field required", "type": "value_error.missing"
        }])
    
    opts = options_from_request(req)
    runner = ExtractorRunner()  # version modifiée comme vous l’avez indiqué (sans storage en param)

    if req.run_async:
        # Déclenche l'extraction en tâche de fond et répond immédiatement
        background.add_task(runner.run_series, req.series, options=opts)
        return {"status": "accepted", "series": req.series, "mode": req.mode, "async": True}
    
    # Exécution synchrone: renvoie le rapport immédiatement
    return runner.run_series(req.series, options=opts)


# http://127.0.0.1:8050/api/corpus/chunk?series=series-20250826-190041-1597 (par phrases (défaut))
# http://127.0.0.1:8050/api/corpus/chunk?series=series-20250826-190041-1597&strategy=paragraph&size=1000&overlap=0 (paragraphe, sans overlap)
# http://127.0.0.1:8050/api/corpus/chunk?series=series-20250826-190041-1597&strategy=recursive&separators=%0A%0A,%0A,.,• (recursive + séparateurs custom)

@router.post("/chunk")
async def run_chunk(
    background: BackgroundTasks,
    series: str = Query(..., description="Série préalablement extraite"),
    strategy: Literal["char","word","sentence","paragraph","line","recursive","tokens","llm"] = Query("sentence"),
    size: int = Query(800, ge=50, le=8000),
    overlap: int = Query(150, ge=0, le=4000),
    separators: Optional[str] = Query(None, description="séparateurs custom (ex: '\\n\\n,\\n,.,•,،')"),
    use_llm: bool = Query(False),
    run_async: bool = Query(True),
):
    opts = ChunkOptions(
        strategy=strategy,
        size=size,
        overlap=overlap,
        separators=tuple([s for s in (separators or "").split(",") if s] ) or ("\n\n","\n",".","•","،"),
        use_llm=use_llm,
    )
    runner = ChunkRunner(opts)

    # dans la route
    def _safe_chunk(series: str):
        try:
            ChunkRunner(opts).run_series(series)
        except Exception:
            import logging; logging.getLogger("chunker").exception("Chunk background failed")

    if run_async:
        background.add_task(_safe_chunk, series)
        # background.add_task(runner.run_series, series)
        return {"status": "accepted", "series": series, "strategy": strategy, "async": True}
    return runner.run_series(series)

@router.post("/embed") # POST /api/corpus/embed avec body { "series": "...", "dimensions": 1536 }
async def embed_series(body: dict = Body(...)):
    series = body.get("series")
    dims = body.get("dimensions")
    # return {"status": "started", "series": series, "dimensions": dims}
    emb = Embedder()
    if not series:
        raise HTTPException(status_code=422, detail="Field 'series' is required")
    return emb.embed_corpus(series, dimensions=dims)

@router.post("/search") # POST /api/corpus/search avec body { "series": "...", "q": "...", "k": 5 }
async def search_series(body: dict = Body(...)):
    series = body.get("series")
    q = body.get("q"); k = int(body.get("k", 5))
    emb = Embedder(provider=get_provider(), db=get_db())
    return emb.search(series, q, k=k)

# POST http://127.0.0.1:8050/api/corpus/kg/build
# asynchrone : {"series":"series-20250826-190041-1597", "limit_chunks": 50, "run_async": true}
# synchrone  : {"series":"series-20250826-190041-1597", "run_async": false, "domain": "immobilier"}

# def _safe_chunk(series: str):
#     try:
#         ChunkRunner(opts).run_series(series)
#     except Exception:
#         import logging; logging.getLogger("chunker").exception("Chunk background failed")

@router.post("/kg/build")
async def build_kg(req: KGBuildRequest, background: BackgroundTasks):
    provider = get_provider()
    runner = KGRunner(provider=provider, db=Neo4jAdapter(),
                      domain_hint=(req.domain or "immobilier"))
    if req.run_async:
        background.add_task(runner.run_series, req.series, limit_chunks=req.limit_chunks)
        return {"status": "accepted", "series": req.series, "async": True}
    return runner.run_series(req.series, limit_chunks=req.limit_chunks)