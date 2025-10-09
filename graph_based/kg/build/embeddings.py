from typing import Dict, List, Tuple
import numpy as np
from adapters.embedding_adapter import get_embedder

def embed_nodes(node_texts: Dict[str, str]) -> Tuple[List[str], np.ndarray]:
    """
    node_texts: id -> display text (name/title/desc).
    """
    embed = get_embedder()
    ids = list(node_texts.keys())
    vecs = np.array([embed(node_texts[i]) for i in ids], dtype="float32")
    return ids, vecs