# corpus/importer.py
from typing import Iterable, List, Tuple
from adapters.storage.base import Storage
from corpus.models import Document

class ImporterService:
    def __init__(self, storage: Storage, allowed_ext: Iterable[str]):
        self.storage = storage
        self.allowed = {e.lower() for e in allowed_ext}

    def import_bytes(self, series: str, files: List[Tuple[str, bytes]]) -> List[Document]:
        docs = []
        for name, data in files:
            if not any(name.lower().endswith(ext) for ext in self.allowed):
                continue
            docs.append(self.storage.put_file(series, name, data))
        return docs

    def list(self, series: str) -> List[Document]:
        return self.storage.list_documents(series)

    def delete(self, series: str, filename: str) -> None:
        self.storage.delete_document(series, filename)

    def merge_series(self, sources: Iterable[str], dest: str) -> List[Document]:
        return self.storage.merge_series(sources, dest)
