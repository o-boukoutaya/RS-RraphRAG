# routes/__init__.py
from fastapi import APIRouter

import routes.corpus as corpus_routes
import routes.health as health_routes
import routes.pipelines as pipelines_routes

api_router = APIRouter(prefix="/api")
api_router.include_router(corpus_routes.router)
api_router.include_router(health_routes.router)
api_router.include_router(pipelines_routes.router)