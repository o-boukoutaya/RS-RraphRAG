# adapters/llm/base.py
# LLM/Embedding : contrat minimal (embed, embed_batch, dim).
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Sequence, Optional, Protocol

class Embedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, text: str) -> List[float]: ...
    
    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]: ...

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...


@dataclass
class EmbedderConfig:
    provider: str = "openai_azure"
    model: str = "text-embedding-3-large"
    api_key: Optional[str] = None
    api_base: Optional[str] = None   # https://{resource}.openai.azure.com
    api_version: str = "2024-02-15-preview"
    dim: int = 0  # 0 => autodetect