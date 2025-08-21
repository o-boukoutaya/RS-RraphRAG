# tests/unit/test_importer.py
from __future__ import annotations
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi import UploadFile
from corpus.importer import Importer
from corpus.storage import LocalStorage


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))

def test_importer_accepts_and_rejects_extensions():
    with TemporaryDirectory() as tmp:
        storage = LocalStorage(Path(tmp))
        imp = Importer(storage, [".txt", ".pdf"]) # autorisés
        files = [
            _upload("a.txt", b"hello"),
            _upload("b.exe", b"oops"),
        ]
        report = imp.import_files("s1", files) # type: ignore[attr-defined]
        # import_files est async -> exécuter réellement
        import asyncio
        report = asyncio.run(report)
        
        assert len(report.accepted) == 1
        assert report.accepted[0].filename == "a.txt"
        assert len(report.rejected) == 1
        assert report.rejected[0].filename == "b.exe"