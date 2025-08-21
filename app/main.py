# app/main.py
from fastapi import FastAPI
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestContextMiddleware
# from app.core.config import get_settings  # si besoin
# Enregistre les extractors au boot :
from corpus.extractor import pdf, docx, csv_txt, xlsx  # noqa: F401
from routes import api_router

setup_logging("INFO")
app = FastAPI()
app.add_middleware(RequestContextMiddleware)
app.include_router(api_router)

log = get_logger(__name__)

# http://127.0.0.1:8050/docs#/