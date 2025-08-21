# adapters/storage/base.py
# storage : root/tmp depuis settings, allow-list, quotas, collisions, create/list/delete/merge, écriture atomique.
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, BinaryIO, Dict
from corpus.models import Document
from dataclasses import dataclass, field

# base.py définit le contrat indépendant du support (FS local, S3…)

class StorageError(Exception): ...
class ExtensionNotAllowed(StorageError): ...
class FileTooLarge(StorageError): ...
class EmptyFile(StorageError): ...

@dataclass(frozen=True)
class StorageConfig:
    root: Path
    tmp_dir: Path
    allowed_extensions: set[str] = field(default_factory=lambda: {".pdf",".txt",".csv",".docx",".xlsx",".xls"})
    max_file_size_mb: int = 64

class Storage(ABC):
    @abstractmethod
    def ensure_series(self, series: str) -> Path: ...

    @abstractmethod
    def put_file(self, series: str, filename: str, data: bytes) -> Document: ...

    @abstractmethod
    def list_documents(self, series: str) -> List[Document]: ...

    @abstractmethod
    def delete_document(self, series: str, filename: str) -> None: ...

    @abstractmethod
    def delete_series(self, series: str) -> None: ...

    @abstractmethod
    def merge_series(self, sources: Iterable[str], dest: str) -> List[Document]: ...
