# corpus/extractor/xlsx.py
from __future__ import annotations
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
        xls = pd.ExcelFile(doc.path)
        blocks: List[TextBlock] = []
        order = 0
        for sheet in xls.sheet_names:
            df = xls.parse(sheet_name=sheet, dtype=str)
            df = df.fillna("")
            cols = list(df.columns)
            def fmt(r): return " | ".join(f"{c}: {str(r.get(c,''))}".strip() for c in cols)
            text = f"# Sheet: {sheet}\n" + "\n".join(fmt(r) for _, r in df.iterrows())
            blocks.append(TextBlock(doc=doc, page=1, order=order, text=text))
            order += 1
        return blocks
