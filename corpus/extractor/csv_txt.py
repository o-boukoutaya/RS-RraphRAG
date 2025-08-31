# corpus/extractor/csv_txt.py
from __future__ import annotations
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
        rows_per_block = max(1, int(self.options.csv_rows_per_block))
        blocks: List[TextBlock] = []
        order = 0
        # on text-ualise pour la suite (chunking, KG) sans perdre l’info de colonnes
        cols = list(df.columns)
        def format_row(s):
            return " | ".join(f"{c}: {str(s.get(c,'')).strip()}" for c in cols)
        for start in range(0, len(df), rows_per_block):
            part = df.iloc[start:start+rows_per_block]
            text = "\n".join(format_row(r) for _, r in part.iterrows())
            blocks.append(TextBlock(doc=doc, page=1, order=order, text=text))
            order += 1
        return blocks

@register(".txt")
class TxtExtractor(BaseExtractor):
    extensions = [".txt"]
    def extract(self, doc: Document) -> List[TextBlock]:
        text = open(doc.path, "r", encoding="utf-8", errors="ignore").read()
        return [TextBlock(doc=doc, page=1, order=0, text=text)]
