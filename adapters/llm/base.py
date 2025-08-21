# adapters/llm/base.py
from abc import ABC, abstractmethod
from typing import List

class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...
