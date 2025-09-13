# graph_based/retriever/vector/dense.py
from typing import List

from corpus.embedder import Embedder
from graph_based.utils.types import ChunkRef

def search(series: str, query: str, *, db, provider, k: int = 6) -> List[ChunkRef]:
    """
    Fallback dense: interroge l'index vectoriel des chunks (réutilise votre corpus/embedder).
    - Output: [{"cid","series","file","page","order","score"}...]
    """
    embedder = Embedder(provider)
    return embedder.search(series, query, k=k)