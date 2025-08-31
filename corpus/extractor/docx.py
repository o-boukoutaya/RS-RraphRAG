# corpus/extractor/docx.py
from __future__ import annotations
from typing import List
from .base import BaseExtractor, _normalize_text
from .registry import register            # ✅ bon module
from corpus.models import Document, TextBlock

@register(".docx")
class DocxExtractor(BaseExtractor):
    extensions = [".docx"]

    def extract(self, doc: Document) -> List[TextBlock]:
        # Alias pour éviter le conflit avec corpus.models.Document
        try:
            from docx import Document as DocxDocument
        except Exception:
            return []

        try:
            d = DocxDocument(doc.path)    # doc.path est str → OK
        except Exception:
            return []

        parts: List[str] = []
        # Paragraphes
        for p in getattr(d, "paragraphs", []):
            t = (getattr(p, "text", "") or "").strip()
            if t: parts.append(t)
        # Tables
        for table in getattr(d, "tables", []):
            for row in getattr(table, "rows", []):
                cells = [(getattr(c, "text", "") or "").replace("\n", " ").strip() for c in row.cells]
                if any(cells):
                    parts.append("| " + " | ".join(cells) + " |")

        text = _normalize_text("\n".join(parts))
        return [TextBlock(doc=doc, page=1, order=0, text=text, bbox=None)] if text else []
