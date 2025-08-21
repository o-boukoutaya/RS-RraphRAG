# corpus/extractor/docx.py
from typing import List
from .base import BaseExtractor
from .registry import register
from corpus.models import Document, TextBlock

@register(".docx")
class DocxExtractor(BaseExtractor):
    extensions = [".docx"]
    def extract(self, doc: Document) -> List[TextBlock]:
        from docx import Document as Docx
        d = Docx(doc.path)
        text = "\n".join(p.text for p in d.paragraphs)
        return [TextBlock(doc=doc, page=1, order=0, text=text)]
