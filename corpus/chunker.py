# corpus/chunker.py
from typing import Iterable, List
from corpus.models import TextBlock, Chunk

def by_tokens(blocks: Iterable[TextBlock], max_tokens=600, overlap=80) -> List[Chunk]:
    # version simple (token = mot). Remplacer par tiktoken au besoin.
    chunks: List[Chunk] = []
    idx = 0
    for b in blocks:
        words = b.text.split()
        start = 0
        while start < len(words):
            end = min(start + max_tokens, len(words))
            text = " ".join(words[start:end])
            chunks.append(Chunk(doc=b.doc, idx=idx, text=text, meta={"page": b.page}))
            idx += 1
            start = end - overlap if end < len(words) else end
    return chunks
