# tests/unit/test_extractor.py
from corpus.models import Document
from corpus.extractor.txt import TxtExtractor  # si tu scindes csv_txt.py

def test_txt_extractor(tmp_path):
    p = tmp_path/"x.txt"; p.write_text("Bonjour", encoding="utf-8")
    doc = Document(series="s", filename="x.txt", path=str(p))
    blocks = TxtExtractor().extract(doc)
    assert blocks and blocks[0].text.strip() == "Bonjour"
