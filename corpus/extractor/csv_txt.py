# corpus/extractor/csv_txt.py
from typing import List
from .base import BaseExtractor
from .registry import register
from corpus.models import Document, TextBlock
import pandas as pd

@register(".csv")
class CsvExtractor(BaseExtractor):
    extensions = [".csv"]
    def extract(self, doc: Document) -> List[TextBlock]:
        df = pd.read_csv(doc.path, dtype=str, keep_default_na=False)
        return [TextBlock(doc=doc, page=1, order=0, text=df.to_csv(index=False))]

@register(".txt")
class TxtExtractor(BaseExtractor):
    extensions = [".txt"]
    def extract(self, doc: Document) -> List[TextBlock]:
        return [TextBlock(doc=doc, page=1, order=0, text=open(doc.path,"r",encoding="utf-8",errors="ignore").read())]
