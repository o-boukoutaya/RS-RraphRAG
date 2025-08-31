# adapters/llm/base.py
from abc import ABC, abstractmethod
from typing import Protocol, Sequence, List, Optional, Iterable, Iterator, Any
import logging
import os

log = logging.getLogger(__name__)

class Provider(Protocol):
    """
    Interface minimale commune à tous les providers.
    - embed / embed_batch : retournent des vecteurs (list[float])
    - ask_llm : retourne un texte (string)
    """

    # ---- Embeddings ----    
    @abstractmethod
    def embed(self, text: str, *, dimensions: Optional[int] = None) -> List[float]: ...

    @abstractmethod
    def embed_batch(self, texts: Sequence[str], *, dimensions: Optional[int] = None) -> List[List[float]]: ...

    def embed_texts(self, texts: List[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        return self.embed_batch(texts, dimensions=dimensions)
    
    # ---- Chat ----
    def ask_llm(self, query: str) -> str: ...

    # ---- Introspection facultative ----
    def capabilities(self) -> dict:
        """
        Renvoie des métadonnées utiles (provider, supports_chat, supports_embeddings, models, dims si connues).
        """
        return {}

# ---------------------- Helpers communs ----------------------

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v


def batch_iter(seq: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    """Découpe une séquence en sous-listes de taille <= size."""
    if size <= 0:
        size = 1
    for i in range(0, len(seq), size):
        yield seq[i:i + size]
