# corpus/extractor/pdf.py
from typing import List
from pathlib import Path
from .base import BaseExtractor
from .registry import register
from corpus.models import Document, TextBlock

@register(".pdf")
class PdfExtractor(BaseExtractor):
    extensions = [".pdf"]

    def extract(self, doc: Document) -> List[TextBlock]:
        blocks: List[TextBlock] = []
        try:
            import pdfplumber
            with pdfplumber.open(doc.path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    txt = page.extract_text() or ""
                    if txt.strip():
                        blocks.append(TextBlock(doc=doc, page=i, order=0, text=txt))
        except Exception:
            pass
        # Fallback OCR si rien trouvé (optionnel, à brancher via config OCR)
        # -> à implémenter plus tard pour éviter dépendance lourde
        return blocks




# OCR FR/AR : on le branche dans un ocr.py (Tesseract/rapidocr) appelé par PdfExtractor seulement quand extract_text() 
# est pauvre et si settings.ocr.enabled=True. On pourra affiner (détection de blocs, tables, sens RTL).