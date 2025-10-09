from fastapi import APIRouter, UploadFile, File, Form
from app.core.logging import setup_logging, get_logger
from app.core.resources import get_all_settings, get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/neo4j", tags=["status"])

@router.get("/") # GET : /neo4j/pingDB
async def test_Neo4J_Cnx():
    from app.core.resources import test_cnx
    return test_cnx()

@router.post("/setup")
async def neo4j_setup() -> dict:
    CONSTRAINTS = [
        "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id_unique  IF NOT EXISTS FOR (c:Chunk)  REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT rel_id_unique    IF NOT EXISTS FOR ()-[r:REL]-() REQUIRE r.id IS UNIQUE",
    ]
    db = get_db()
    out = []
    for q in CONSTRAINTS:
        out.append(db.run_cypher(q))
    return {"status":"ok","applied": len(CONSTRAINTS), "details": out}


@router.post("/cypher") # POST : /neo4j/cypher
async def run_cypher(query: str):
    db = get_db()
    try:
        result = db.run_cypher(query)
        # return result
        return {"result": [dict(r) for r in result]}
    except Exception as e:
        logger.error(f"Error running cypher query: {e}")
        return {"error": str(e)}