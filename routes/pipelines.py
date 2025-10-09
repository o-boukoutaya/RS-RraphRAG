from importlib.resources import files
from fastapi import APIRouter, Body, UploadFile, File, Form
from app.core.resources import get_provider, get_db
from app.core.logging import get_logger
from graph_based.kg.community import hierarchy, leiden
from graph_based.utils.types import BuildReport
from graph_based.kg.build import canonicalize, graph_store
from graph_based.kg.el import augment


router = APIRouter(prefix="/pipelines", tags=["pipelines"])
logger = get_logger(__name__)

@router.get("/") # get http://localhost:8000/api/pipelines/
async def list_pipelines():
    return {"pipelines": []}

# -----------------------------------------------------------------------------------

# Le processus de construction du KG tout entier
@router.post("/graph/build")
async def build_graph_pipeline(series: str, options: dict) -> BuildReport:
    from pipelines.build_graph import run as build_run
    return build_run(series=series, options=options)

# -----------------------------------------------------------------------------------


@router.get("/list_chunks") # get http://localhost:8000/api/pipelines/list_chunks
async def list_chunks():
    serie = "series-20250913-175435-c30e"
    db = get_db()
    chunks = db.stream_chunks(serie)
    return {"serie": serie, "chunks": chunks}

@router.post("/step1/canonicalize")
async def step1_canonicalize(params: dict = Body(...)):
    series = params.get("series")
    nodes, edges = canonicalize.run(series, min_conf=params.get("min_conf",0.35))
    return {"nodes": len(nodes), "edges": len(edges)}

@router.post("/step2/augment")
async def step2_augment(params: dict = Body(...)):
    series = params.get("series")
    nodes, edges = canonicalize.run(series, min_conf=params.get("min_conf",0.35))
    nodes, edges = augment.run(series, nodes, edges)
    return {"nodes": len(nodes), "edges": len(edges)}

@router.post("/step3/graph_store")
async def step3_graph_store(params: dict = Body(...)):
    series = params.get("series")
    nodes, edges = canonicalize.run(series, min_conf=params.get("min_conf",0.35))
    nodes, edges = augment.run(series, nodes, edges)
    write = graph_store.upsert(series, nodes, edges)
    return write
    
@router.post("/step4/leiden")
async def step4_leiden(params: dict = Body(...)):
    series = params.get("series")
    options = params.get("options", {})
    # comms = leiden.detect(series, levels=options.get("community", {}).get("levels", 3), resolution=options.get("community", {}).get("resolution", 1.2))
    rows = leiden.detect(series, levels=options["community"]["levels"], resolution=options["community"]["resolution"])
    return rows

@router.post("/step5/hierarchy")
async def step5_hierarchy(params: dict = Body(...)):
    series = params.get("series")
    options = params.get("options", {})
    comms = leiden.detect(series, levels=options["community"]["levels"], resolution=options["community"]["resolution"])
    return hierarchy.wire(series, comms, db=get_db())