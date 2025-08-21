# corpus/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class Document:
    series: str
    filename: str
    path: str
    mime: Optional[str] = None
    meta: Dict = field(default_factory=dict)

@dataclass
class TextBlock:
    doc: Document
    page: int
    order: int
    text: str
    bbox: Optional[Tuple[float,float,float,float]] = None
    lang: Optional[str] = None

@dataclass
class Chunk:
    doc: Document
    idx: int
    text: str
    meta: Dict = field(default_factory=dict)
    