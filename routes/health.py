from fastapi import APIRouter, UploadFile, File, Form
from app.core.logging import setup_logging, get_logger
from app.core.resources import get_all_settings

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check():
    logger.info("health check")
    return {"status": "healthy"}

# @router.get("/pingDB") # GET : /health/pingDB
# async def test_Neo4J_Cnx():
#     from app.core.resources import test_cnx
#     return test_cnx()

@router.get("/db-config") # GET : /health/db-config
async def get_db_config():
    db = get_all_settings().neo4j
    return db

@router.get("/provider") # GET : /health/provider
async def get_provider_config():
    provider = get_all_settings().provider.default
    return provider

@router.get("/settings") # GET : /health/settings
async def get_all_config():
    settings = get_all_settings()
    return settings

@router.get("/ask-llm-test") # GET : /health/ask-llm
async def get_answer():
    logger.info("GET:ask-llm-test:start", extra={})
    from app.core.resources import ask_llm
    resp = ask_llm("Quelle est la capitale de la France?")
    logger.info("GET:ask-llm-test:end", extra={"resp": resp})
    return resp


@router.get("/get-test-embd") # GET : /health/get-test-embd
async def get_test_embd():
    logger.info("GET:get-test-embd:start", extra={})
    from app.core.resources import get_provider
    provider = get_provider()
    vector = provider.embed("Bonjour, je m'appelle Oussama.")
    logger.info("GET:get-test-embd:end", extra={"vector": vector})
    return vector
