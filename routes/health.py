from fastapi import APIRouter, UploadFile, File, Form
from app.core.logging import setup_logging, get_logger

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger(__name__)

@router.get("/")
async def health_check():
    log.info("health check")
    return {"status": "healthy"}
