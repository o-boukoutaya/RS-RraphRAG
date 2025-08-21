# tests/unit/test_importer.py
from adapters.storage.local import LocalStorage
from corpus.importer import ImporterService

def test_importer_roundtrip(tmp_path):
    storage = LocalStorage(tmp_path/"data", tmp_path/"tmp")
    svc = ImporterService(storage, [".txt"])
    docs = svc.import_bytes("s1", [("a.txt", b"hello"), ("b.pdf", b"%PDF")])
    assert [d.filename for d in docs] == ["a.txt"]
    assert len(storage.list_documents("s1")) == 1
