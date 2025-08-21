from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

@router.get("/")
async def list_pipelines():
    return {"pipelines": []}
