# adapters/vector/base.py
from abc import ABC, abstractmethod
from typing import List, Tuple

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, items: List[Tuple[str, str]]): ...
    @abstractmethod
    def search(self, query: str, k: int = 8): ...
