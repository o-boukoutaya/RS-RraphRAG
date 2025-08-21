# corpus/storage.py (remplace la classe LocalStorage)
from __future__ import annotations
import os, shutil, mimetypes, hashlib
from pathlib import Path
from fastapi import UploadFile
from .models import Document

class LocalStorage:
    def __init__(self, root: Path, series_dirname: str = "series", tmp_dir: Path | None = None) -> None:
        self.root = Path(root)
        self.series_dir = self.root / series_dirname
        self.tmp_dir = Path(tmp_dir) if tmp_dir else self.root / "_tmp"
        self.series_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def ensure_series(self, series: str) -> Path:
        p = self.series_dir / series
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _safe_name(name: str) -> str:
        return Path(name or "file").name

    @staticmethod
    def _resolve_collision(p: Path) -> Path:
        if not p.exists():
            return p
        i = 1
        while True:
            cand = p.with_name(f"{p.stem}__{i}{p.suffix}")
            if not cand.exists():
                return cand
            i += 1

    async def save_upload(self, series: str, upload: UploadFile) -> Document:
        series_dir = self.ensure_series(series)
        safe_filename = self._safe_name(upload.filename)
        target = self._resolve_collision(series_dir / safe_filename)

        tmp_target = self.tmp_dir / f".{target.name}.part"
        tmp_target.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        size = 0
        with tmp_target.open("wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
                sha256.update(chunk)

        await upload.close()
        os.replace(tmp_target, target)  # move atomique si même volume

        mime, _ = mimetypes.guess_type(target.name)
        return Document(
            series=series,
            filename=target.name,
            path=str(target.resolve()),
            size=size,
            mime=mime,
            sha256=sha256.hexdigest(),
        )
