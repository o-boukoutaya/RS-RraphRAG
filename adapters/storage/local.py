# adapters/storage/local.py
# storage : root/tmp depuis settings, allow-list, quotas, collisions, create/list/delete/merge, écriture atomique.
from __future__ import annotations
import re, shutil
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, BinaryIO
from .base import StorageConfig, StorageError, ExtensionNotAllowed, FileTooLarge, EmptyFile


# À noter :
#   - Root/tmp branchés à settings.storage.
#   - Allow-list d’extensions normalisées en lowercase.
#   - Quotas via max_file_size_mb.
#   - Collision → suffixe __1, __2, …
#   - Méthodes create/list/delete/merge incluses.
# On peut laisser notre corpus.storage.LocalStorage en prod et tester ce nouvel adapter en parallèle : API compatible.


def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("._")
    return name or "file"

def normalize_ext(name: str) -> str:
    return Path(name).suffix.lower()

class LocalStorage:
    """API compatible avec ton `corpus.storage.LocalStorage` pour une migration douce."""

    def __init__(self, cfg: StorageConfig):
        self.cfg = cfg
        self.root = Path(cfg.root)
        self.tmp = Path(cfg.tmp_dir)
        self.series_root = self.root / "series"
        for p in (self.root, self.tmp, self.series_root):
            p.mkdir(parents=True, exist_ok=True)

    # ------------ séries
    def series_dir(self, series: str) -> Path:
        return self.series_root / series

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
                    d = self.series_dir(series); i += 1
            else:
                raise FileExistsError(f"Series '{series}' already exists")
        d.mkdir(parents=True, exist_ok=True)
        return series

    def list_series(self) -> list[str]:
        if not self.series_root.exists(): return []
        return sorted([p.name for p in self.series_root.iterdir() if p.is_dir()])

    def delete_series(self, series: str) -> int:
        d = self.series_dir(series)
        if not d.exists(): return 0
        count = sum(1 for f in d.rglob("*") if f.is_file())
        shutil.rmtree(d, ignore_errors=True)
        return count

    def merge_series(self, target: str, sources: Iterable[str], *, on_conflict="suffix") -> int:
        tgt = self.series_dir(target); tgt.mkdir(parents=True, exist_ok=True)
        moved = 0
        for s in sources:
            sd = self.series_dir(s)
            if not sd.exists(): continue
            for f in sd.iterdir():
                if not f.is_file(): continue
                dest = tgt / f.name
                if dest.exists() and on_conflict == "suffix":
                    dest = self._resolve_collision(dest)
                shutil.move(str(f), str(dest)); moved += 1
            shutil.rmtree(sd, ignore_errors=True)
        return moved

    # ------------ fichiers
    def save_stream(self, series: str, filename: str, stream: BinaryIO) -> Path:
        safe = sanitize_filename(filename)
        ext = normalize_ext(safe)
        if ext not in self.cfg.allowed_extensions:
            raise ExtensionNotAllowed(ext)

        self.series_dir(series).mkdir(parents=True, exist_ok=True)
        tmp = self.tmp / f"{uuid4().hex}{ext}"
        with open(tmp, "wb") as out:
            shutil.copyfileobj(stream, out)

        size = tmp.stat().st_size
        if size == 0:
            tmp.unlink(missing_ok=True); raise EmptyFile(safe)
        if self.cfg.max_file_size_mb and size > self.cfg.max_file_size_mb * 1024 * 1024:
            tmp.unlink(missing_ok=True); raise FileTooLarge(f"{safe} ({size} B)")

        final = self._resolve_collision(self.series_dir(series) / safe)
        tmp.replace(final)
        return final

    def _resolve_collision(self, path: Path) -> Path:
        if not path.exists(): return path
        stem, ext = path.stem, path.suffix
        i = 1
        while True:
            c = path.with_name(f"{stem}__{i}{ext}")
            if not c.exists(): return c
            i += 1

    # ----------- fabrique
    @classmethod
    def from_settings(cls, settings) -> "LocalStorage":
        s = settings.storage
        return cls(StorageConfig(
            root=Path(s.root),
            tmp_dir=Path(s.tmp_dir),
            allowed_extensions={e.lower() for e in s.allowed_extensions},
            max_file_size_mb=int(getattr(s, "max_file_size_mb", 64)),
        ))
