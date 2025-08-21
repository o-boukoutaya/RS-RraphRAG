# adapters/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List
from corpus.models import Document

# base.py définit le contrat indépendant du support (FS local, S3…)

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
