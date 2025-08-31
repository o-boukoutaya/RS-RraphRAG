# adapters/storage/local.py
from __future__ import annotations

import os
import re
import shutil
import hashlib
import mimetypes
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, BinaryIO, Sequence, List

from fastapi import UploadFile

from .base import StorageError, ExtensionNotAllowed,  FileTooLarge, EmptyFile, Storage        # <- ABC que l’on implémente réellement ici

from corpus.models import Document
from app.core.config import get_settings, StorageCfg

# ----------------------- utilitaires -----------------------
def sanitize_filename(name: str) -> str:
    name = Path(name or "file").name
    # remplace séparateurs et espaces multiples
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("._")
    return name or "file"


def normalize_ext(name: str) -> str:
    # garantit un suffixe en lowercase avec le point
    ext = Path(name).suffix.lower()
    return ext


class LocalStorage(Storage):
    """
    Implémentation disque locale du contrat Storage:
    - Root/tmp branchés à settings.storage.
    - Allow-list d’extensions normalisées en lowercase.
    - Quotas via max_file_size_mb.
    - Collision → suffixe __1, __2, …
    - Méthodes create/list/delete/merge incluses.
    """

    def __init__(self, cfg: Optional[StorageCfg] = None) -> None:
        self.cfg: StorageCfg = cfg or get_settings().storage  # Pydantic model
        self.root: Path = Path(self.cfg.root)
        self.series: Path = self.root / self.cfg.series_dirname
        self.tmp: Path = Path(self.cfg.tmp_dir)

        # normalise la liste des extensions autorisées
        self.allowed: set[str] = {str(e).lower() for e in self.cfg.allowed_extensions}
        # s’assure que chaque extension commence par un point
        self.allowed = {e if e.startswith(".") else f".{e}" for e in self.allowed}

        for p in (self.root, self.tmp, self.series):
            p.mkdir(parents=True, exist_ok=True)

        # taille max en octets (0/None => illimité)
        self._max_bytes: Optional[int] = None
        if getattr(self.cfg, "max_file_size_mb", None):
            self._max_bytes = int(self.cfg.max_file_size_mb) * 1024 * 1024

    # ----------------- gestion des séries -----------------
    def series_dir(self, series: str) -> Path:
        return self.series / series
    
    def ensure_series(self, series: str) -> Path:
        d = self.series_dir(series)
        d.mkdir(parents=True, exist_ok=True)
        return d
    
    def create_series(self, series: Optional[str] = None, *, on_conflict: str = "suffix") -> str:
        if not series:
            series = datetime.now().strftime("%Y%m%d-%H%M%S")
        d = self.series_dir(series)
        if d.exists():
            if on_conflict == "suffix":
                base = series
                i = 1
                while d.exists():
                    series = f"{base}__{i}"
                    d = self.series_dir(series)
                    i += 1
            else:
                raise FileExistsError(f"Series '{series}' already exists")
        d.mkdir(parents=True, exist_ok=True)
        return series

    def list_series(self) -> list[str]:
        if not self.series.exists(): return []
        return sorted([p.name for p in self.series.iterdir() if p.is_dir()])
    
    def delete_series(self, series: str) -> int:
        d = self.series_dir(series)
        if not d.exists():
            return 0
        count = sum(1 for f in d.rglob("*") if f.is_file())
        shutil.rmtree(d, ignore_errors=True)
        return count
    
    def merge_series(self, target: str, sources: Iterable[str], *, on_conflict: str = "suffix") -> int:
        tgt = self.ensure_series(target)
        moved = 0
        for s in sources:
            sd = self.series_dir(s)
            if not sd.exists():
                continue
            for f in sd.iterdir():
                if not f.is_file():
                    continue
                dest = tgt / f.name
                if dest.exists() and on_conflict == "suffix":
                    dest = self._resolve_collision(dest)
                shutil.move(str(f), str(dest))
                moved += 1
            shutil.rmtree(sd, ignore_errors=True)
        return moved

    @staticmethod
    def _safe_name(name: str) -> str:
        return Path(name or "file").name

    @staticmethod
    def _resolve_collision(path: Path) -> Path:
        if not path.exists(): return path
        stem, ext = path.stem, path.suffix
        i = 1
        while True:
            c = path.with_name(f"{stem}__{i}{ext}")
            if not c.exists(): return c
            i += 1

    # ----------------- fichiers (contrat Storage) -----------------
    async def save_upload(self, series: str, upload: UploadFile) -> Document:
        """
        Chemin “web” pratique pour UploadFile (FastAPI).
        """
        series_dir = self.ensure_series(series)
        safe_filename = sanitize_filename(upload.filename or "file")
        ext = normalize_ext(safe_filename)
        if self.allowed and ext not in self.allowed:
            await upload.close()
            raise ExtensionNotAllowed(ext)
        
        target = self._resolve_collision(series_dir / safe_filename)
        tmp_target = self.tmp / f".{target.name}.part"
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
    
    def save_stream(self, series: str, filename: str, stream: BinaryIO) -> Path:
        """
        Helper bas niveau pour écrire depuis un flux.
        """
        safe = sanitize_filename(filename)
        ext = normalize_ext(safe)
        if self.allowed and ext not in self.allowed:
            raise ExtensionNotAllowed(ext)

        self.ensure_series(series)
        tmp = self.tmp / f"{uuid4().hex}{ext}"
        tmp.parent.mkdir(parents=True, exist_ok=True)

        with open(tmp, "wb") as out:
            shutil.copyfileobj(stream, out)

        size = tmp.stat().st_size
        if size == 0:
            tmp.unlink(missing_ok=True)
            raise EmptyFile(safe)
        if self._max_bytes and size > self._max_bytes:
            tmp.unlink(missing_ok=True)
            raise FileTooLarge(f"{safe} ({size} B)")

        final = self._resolve_collision(self.series_dir(series) / safe)
        tmp.replace(final)
        return final

    

    # ====== Méthodes requises par l’ABC Storage ======
    def put_stream(self, series: str, filename: str, stream: BinaryIO) -> Document:
        """
        Implémentation contractuelle mappe sur save_stream.
        """
        final = self.save_stream(series, filename, stream)
        size = final.stat().st_size
        mime, _ = mimetypes.guess_type(final.name)
        # sha256 (optionnel pour put_stream)
        sha256 = hashlib.sha256()
        with open(final, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                sha256.update(chunk)

        return Document(
            series=series,
            filename=final.name,
            path=str(final.resolve()),
            size=size,
            mime=mime,
            sha256=sha256.hexdigest(),
        )


    def put_file(self, series: str, file_path: str | Path, *, filename: Optional[str] = None) -> Document:
        """
        Copie un fichier existant dans la série (contrat Storage).
        """
        src = Path(file_path)
        if not src.is_file():
            raise StorageError(f"Source file not found: {src}")

        # Le nom cible peut être forcé
        name = sanitize_filename(filename or src.name)
        with open(src, "rb") as f:
            return self.put_stream(series, name, f)

    def list_documents(self, series: str) -> list[Document]:
        """
        Liste les documents d’une série (contrat Storage).
        """
        d = self.series_dir(series)
        if not d.exists():
            return []
        docs: list[Document] = []
        for f in sorted(p for p in d.iterdir() if p.is_file()):
            size = f.stat().st_size
            mime, _ = mimetypes.guess_type(f.name)
            docs.append(
                Document(
                    series=series,
                    filename=f.name,
                    path=str(f.resolve()),
                    size=size,
                    mime=mime,
                    sha256="",  # optionnel : on ne recalcule pas systématiquement ici
                )
            )
        return docs

    def delete_document(self, series: str, filename: str) -> bool:
        """
        Supprime un document (contrat Storage).
        """
        f = self.series_dir(series) / sanitize_filename(filename)
        if not f.exists() or not f.is_file():
            return False
        try:
            f.unlink()
            return True
        except OSError as e:
            raise StorageError(str(e)) from e

    # ----------- fabrique optionnelle -----------
    @classmethod
    def from_settings(cls) -> "LocalStorage":
        """
        Instancie depuis la config globale (syntactic sugar).
        """
        return cls(get_settings().storage)
    
    