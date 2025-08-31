from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

Mode = Literal["kg", "dense", "hybrid"]

class SearchRequest(BaseModel):
    query: str
    mode: Mode = "hybrid"
    k: int = 6
    series: Optional[str] = None
    index_name: Optional[str] = None       # ex: "chunk_embedding_idx"
    filters: Dict[str, Any] = Field(default_factory=dict)  # ex: {"type": "Project"}

class Hit(BaseModel):
    id: str
    score: float
    text: Optional[str] = None
    page: Optional[int] = None
    filename: Optional[str] = None
    label: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class SearchResponse(BaseModel):
    query: str
    mode: Mode
    hits: List[Hit]
    cypher: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
