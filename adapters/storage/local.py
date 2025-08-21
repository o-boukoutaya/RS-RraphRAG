# adapters/storage/local.py
from __future__ import annotations
import os, shutil
from pathlib import Path
from typing import Iterable, List
from .base import Storage
from corpus.models import Document

# local.py implémente ce contrat sur le système de fichiers.
# Storage base/local : base = contrat; local = FS. Plus tard tu ajoutes S3Storage sans toucher au métier.

class LocalStorage(Storage):
    def __init__(self, root: str, tmp: str):
        self.root = Path(root); self.tmp = Path(tmp)
        self.root.mkdir(parents=True, exist_ok=True)
        self.tmp.mkdir(parents=True, exist_ok=True)

    def ensure_series(self, series: str) -> Path:
        p = self.root / series
        p.mkdir(parents=True, exist_ok=True)
        return p

    def put_file(self, series: str, filename: str, data: bytes) -> Document:
        series_dir = self.ensure_series(series)
        safe = Path(filename).name
        dst = series_dir / safe
        tmp = self.tmp / (safe + ".part")
        with open(tmp, "wb") as f: f.write(data)
        os.replace(tmp, dst)  # atomic
        return Document(series=series, filename=safe, path=str(dst))

    def list_documents(self, series: str) -> List[Document]:
        series_dir = self.ensure_series(series)
        docs = []
        for p in series_dir.iterdir():
            if p.is_file():
                docs.append(Document(series=series, filename=p.name, path=str(p)))
        return docs

    def delete_document(self, series: str, filename: str) -> None:
        p = self.root / series / filename
        if p.exists(): p.unlink()

    def delete_series(self, series: str) -> None:
        p = self.root / series
        if p.exists(): shutil.rmtree(p)

    def merge_series(self, sources: Iterable[str], dest: str) -> List[Document]:
        dest_dir = self.ensure_series(dest)
        out = []
        for s in sources:
            src = self.root / s
            if not src.exists(): continue
            for p in src.iterdir():
                if p.is_file():
                    target = dest_dir / p.name
                    if target.exists():
                        # dédoublonnage simple
                        target = dest_dir / f"{p.stem}__{s}{p.suffix}"
                    shutil.move(str(p), str(target))
                    out.append(Document(series=dest, filename=target.name, path=str(target)))
            shutil.rmtree(src, ignore_errors=True)
        return out
