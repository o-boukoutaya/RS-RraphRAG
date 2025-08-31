# corpus/extractor/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Set, Tuple
import unicodedata, re

from corpus.models import ExtractRequest
from corpus.models import Document, TextBlock

# zones Unicode "Private Use"
_PUA_RANGES = (
    (0xE000, 0xF8FF),        # BMP PUA
    (0xF0000, 0xFFFFD),      # Plane 15
    (0x100000, 0x10FFFD),    # Plane 16
)

@dataclass
class ExtractOptions:
    # "auto": heuristique; "linked": un bloc global; "per_page": un bloc par page
    mode: str = "auto" # "auto" | "linked" | "per_page"
    include_pages: Optional[Sequence[int]] = None   # ex: [1,2,3]
    exclude_pages: Set[int] = field(default_factory=set)
    # OCR
    ocr_enabled: bool = False
    ocr_languages: Tuple[str, ...] = ("eng",) #Sequence[str] = ("eng",)
    # Données tabulaires volumineuses
    csv_rows_per_block: int = 200

def _allowed_page(i: int, total: int, include: Optional[Sequence[int]], exclude: Set[int]) -> bool:
    if include:
        return i in include and i not in exclude
    return i not in exclude

def _parse_ranges(spec: Optional[str]) -> Optional[List[int]]:
    """parse '1,2,5-8,10-' -> [1,2,5,6,7,8,10,11,...] (borne haute non bornée ignorée)"""
    if not spec:
        return None
    out: Set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = a.strip()
            b = b.strip()
            if a and b:
                out.update(range(int(a), int(b) + 1))
            elif a and not b:
                # "10-" => borne ouverte : on l’ignore côté API (évite explosion)
                out.add(int(a))
        else:
            out.add(int(part))
    return sorted(out) if out else None

def _parse_langs(spec: str) -> Tuple[str, ...]:
    return tuple(x.strip() for x in (spec or "eng").split(",") if x.strip()) or ("eng",)

# Conversion Request -> Options (évite toute logique dans la route)
def options_from_request(req: "ExtractRequest") -> ExtractOptions:
    from corpus.models import ExtractRequest  # import local pour éviter cycles
    assert isinstance(req, ExtractRequest)
    return ExtractOptions(
        mode=req.mode,
        include_pages=_parse_ranges(req.include_pages),
        exclude_pages=set(_parse_ranges(req.exclude_pages) or []),
        ocr_enabled=req.ocr,
        ocr_languages=_parse_langs(req.ocr_langs),
    )

# Normalisation du texte extrait
# Cette normalisation sera utilisée par les extracteurs (PDF/DOCX).
def _normalize_text(text: str) -> str:
    """Nettoie le texte pour RAG: NFKC, retire contrôles/PUA, répare césures, compacte espaces."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    # garder \n et \t, retirer le reste des contrôles
    t = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", t)
    # supprimer Private Use Area (glyphes exotiques)
    t = "".join(ch for ch in t if not any(a <= ord(ch) <= b for a, b in _PUA_RANGES))
    # normaliser retours ligne
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # réparer césure "mot-\nmot" -> "motmot"
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    # compacter espaces mais préserver \n
    t = re.sub(r"[ \t]+", " ", t)
    # limiter les multiples sauts à 2
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

class BaseExtractor(ABC):
    """
    Classe de base pour les extracteurs de documents.
    """
    extensions: Iterable[str] = ()

    def __init__(self, options: Optional[ExtractOptions] = None) -> None:
        self.options = options or ExtractOptions()

    @abstractmethod
    def extract(self, doc: Document) -> List[TextBlock]: ...