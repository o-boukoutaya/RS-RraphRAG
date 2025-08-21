# app/main.py
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from routes import corpus as corpus_routes

def create_app():
    setup_logging()
    app = FastAPI(title="RS-RRAPHrag v2")
    app.add_middleware(RequestContextMiddleware)
    app.include_router(corpus_routes.router)
    return app

app = create_app()

if __name__ == "__main__":
    s = get_settings()
    import uvicorn
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=s.dev_reload)
