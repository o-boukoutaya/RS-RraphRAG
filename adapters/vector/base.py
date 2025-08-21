# adapters/vector/base.py
# vector : contrat de retour standard (VectorHit avec id, score, metadata) + index mémoire prêt pour tests; dimension provenant de l’embedder.
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Sequence, Tuple
import math

@dataclass
class VectorHit:
    """ Représente un résultat de recherche dans l'index vectoriel."""
    id: str
    score: float
    metadata: Dict

class VectorIndex:
    """ Classe abstraite pour l'indexation vectorielle.
        Les implémentations concrètes doivent fournir des méthodes pour ajouter des vecteurs et effectuer des recherches.
    """
    dim: int
    def add(self, ids: Sequence[str], vectors: Sequence[Sequence[float]], metadata: Sequence[Dict] | None = None): ...
    def search(self, query: Sequence[float], k: int = 8) -> List[VectorHit]: ...

class InMemoryIndex(VectorIndex):
    """Brute-force cosine — suffisant pour tests et petits volumes."""
    def __init__(self, dim: int):
        self.dim = dim
        self._vecs: Dict[str, List[float]] = {}
        self._meta: Dict[str, Dict] = {}

    def add(self, ids, vectors, metadata=None):
        if metadata is None: metadata = [{}] * len(ids)
        for i, v, m in zip(ids, vectors, metadata):
            if len(v) != self.dim:
                raise ValueError(f"dim mismatch: expected {self.dim}, got {len(v)}")
            self._vecs[i] = list(v); self._meta[i] = dict(m)

    def search(self, query, k=8) -> List[VectorHit]:
        def cos(a,b):
            dp = sum(x*y for x,y in zip(a,b))
            na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
            return 0.0 if na==0 or nb==0 else dp/(na*nb)
        scores = [(i, cos(query, v)) for i, v in self._vecs.items()]
        scores.sort(key=lambda t: t[1], reverse=True)
        return [VectorHit(id=i, score=s, metadata=self._meta[i]) for i, s in scores[:k]]
