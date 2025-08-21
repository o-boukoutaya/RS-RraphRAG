# corpus/models.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

class Document(BaseModel):
    series: str
    filename: str
    path: str                # ← string côté API
    size: Optional[int] = None
    mime: Optional[str] = None
    sha256: Optional[str] = None
    meta: Dict = Field(default_factory=dict)

class TextBlock(BaseModel):
    doc: Document
    page: int | None = None
    order: int | None = None
    text: str
    bbox: Tuple[float, float, float, float] | None = None
    lang: str | None = None

class Chunk(BaseModel):
    doc: Document
    idx: int
    text: str
    meta: Dict = Field(default_factory=dict)

class RejectedFile(BaseModel):
    filename: str
    reason: str
    # timestamp: float

class ImportReport(BaseModel):
    series: str
    accepted: List[Document] = Field(default_factory=list)
    rejected: List[RejectedFile] = Field(default_factory=list)