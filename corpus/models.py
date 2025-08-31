# corpus/models.py
from __future__ import annotations
# from curses import meta
from typing import Dict, List, Optional, Tuple, Literal
from pydantic import BaseModel, Field

class Document(BaseModel):
    series: str
    filename: str
    path: str                # ← string côté API
    size: Optional[int] = None
    mime: Optional[str] = None
    sha256: Optional[str] = None
    meta: Dict = Field(default_factory=dict)

class ExtractRequest(BaseModel):
    series: Optional[str] = None
    mode: Literal["auto", "linked", "per_page"] = "auto"
    include_pages: Optional[str] = None     # ex: "1,2,5-8"
    exclude_pages: Optional[str] = None     # ex: "3,4"
    ocr: bool = False
    ocr_langs: str = "eng"                  # ex: "eng,fra"
    run_async: bool = True

class TextBlock(BaseModel):
    doc: Document
    page: int | None = None
    order: int | None = None
    text: str
    bbox: Tuple[float, float, float, float] | None = None
    lang: str | None = None
    meta: Dict = Field(default_factory=dict)
    

class Chunk(BaseModel):
    doc: Document
    idx: int
    text: str
    meta: Dict = Field(default_factory=dict)

class RejectedFile(BaseModel):
    filename: str
    reason: Optional[str] = None
    message: Optional[str] = None
    # timestamp: float

class ImportReport(BaseModel):
    series: str
    accepted: List[Document] = Field(default_factory=list)
    rejected: List[RejectedFile] = Field(default_factory=list)

class KGBuildRequest(BaseModel):
    series: str
    limit_chunks: Optional[int] = None
    run_async: bool = True
    domain: Optional[str] = None  # "immobilier" (défaut), "general", "cv", ...
    # (optionnel) on pourrait ajouter: provider="gemini|azure|phi" ; pour l'instant on utilise get_provider()