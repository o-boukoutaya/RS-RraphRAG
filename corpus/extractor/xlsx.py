# corpus/extractor/xlsx.py
from typing import List
from .base import BaseExtractor
from .registry import register
from corpus.models import Document, TextBlock
import pandas as pd

@register(".xlsx")
@register(".xls")
class XlsxExtractor(BaseExtractor):
    extensions = [".xlsx",".xls"]
    def extract(self, doc: Document) -> List[TextBlock]:
        df = pd.read_excel(doc.path, dtype=str)
        return [TextBlock(doc=doc, page=1, order=0, text=df.to_csv(index=False))]
