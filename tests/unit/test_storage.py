from corpus.storage import FileStorage
from pathlib import Path


def test_create_series_and_save_bytes(tmp_path):
    storage = FileStorage(root=tmp_path)
    sid = storage.create_series()
    p = storage.save_bytes(sid, "hello.txt", b"salut")
    assert p.exists()
    assert (tmp_path / sid / "raw" / p.name).exists()
