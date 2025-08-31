# tests/unit/test_embedder_fake.py
import json
from pathlib import Path
from corpus.embedder import Embedder
from app.core.resources import get_provider, get_storage

# --- fakes ---
class FakeProvider:
    embed_model = "fake-emb"
    def embed(self, text: str, *, dimensions=None):
        # vecteur simple & deterministic (longueur 8)
        return [float((ord(c) % 13))/13.0 for c in (text + " "*8)[:8]]
    def embed_batch(self, texts, *, dimensions=None):
        return [self.embed(t) for t in texts]
    def ask_llm(self, q: str): return "ok"

class FakeDB:
    def __init__(self):
        self.rows = []
        self.index_created = None
        self.index_exists = False
    def check_index_exists(self, name): return self.index_exists
    def create_vector_index(self, name, *, label, prop, dimensions, similarity):
        self.index_created = (name, label, prop, dimensions, similarity)
        self.index_exists = True
    def upsert_chunks(self, rows, *, label, prop):
        self.rows.extend(rows); return len(rows)
    def query_top_k(self, index, vec, *, k, series):
        # renvoie les 2 premiers rows comme hits simulés
        return [{"id": r["cid"], "text": r["text"], "score": 0.9} for r in self.rows[:min(k,2)}]

def test_embedder_ingest_tmp(tmp_path: Path, monkeypatch):
    # fabrique une série temporaire avec un fichier chunks.jsonl
    series = "s1"
    storage = get_storage()
    series_dir = storage.ensure_series(series)
    chunks_dir = series_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # faux report
    (chunks_dir / "_report.json").write_text(
        json.dumps({"series": series, "items": [{"output": "chunks/f.chunks.jsonl"}]}),
        encoding="utf-8"
    )
    # faux chunks
    with (chunks_dir / "f.chunks.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({"doc":{"series":series,"filename":"f.pdf"},"text":"hello","order":0,"meta":{"page":1}})+"\n")
        f.write(json.dumps({"doc":{"series":series,"filename":"f.pdf"},"text":"world","order":1,"meta":{"page":1}})+"\n")

    # monkeypatch LocalStorage pour que l'Embedder utilise tmp_path
    monkeypatch.setattr("embedder.storage", lambda: get_storage())  #LocalStorage(root=str(tmp_path)))

    emb = Embedder(provider=FakeProvider(), db=FakeDB(), batch_size=2)
    rep = emb.embed_corpus(series)

    assert rep["vectors"] == 2
    assert rep["dimensions"] == 8
    assert emb.db.index_created[0].startswith("chunkIndex__")
    assert len(emb.db.rows) == 2
