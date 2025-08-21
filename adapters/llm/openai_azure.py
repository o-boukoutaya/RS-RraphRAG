# adapters/llm/openai_azure.py
# # LLM/Embedding : implémentation Azure OpenAI (héritage explicite).
from __future__ import annotations
from typing import List, Sequence
from dataclasses import dataclass
import logging

from .base import Embedder, EmbedderConfig

log = logging.getLogger("embedder")

try:
    from openai import AzureOpenAI
except Exception:  # lib non installée
    AzureOpenAI = None

@dataclass
class AzureOpenAIEmbedder(Embedder):
    cfg: EmbedderConfig
    client: AzureOpenAI
    name: str = "openai_azure"
    dim: int = 0

    @classmethod
    def from_settings(cls, settings) -> "AzureOpenAIEmbedder":
        cfg = EmbedderConfig(
            provider="openai_azure",
            model=settings.llm.embedder.model,
            api_key=settings.llm.embedder.api_key,
            api_base=settings.llm.embedder.api_base,
            api_version=settings.llm.embedder.api_version,
            dim=int(getattr(settings.llm.embedder, "dim", 0)),
        )
        if AzureOpenAI is None:
            raise RuntimeError("openai package missing. Add 'openai' to requirements.")
        client = AzureOpenAI(api_key=cfg.api_key, api_version=cfg.api_version, base_url=cfg.api_base)
        emb = cls(cfg=cfg, client=client)
        if cfg.dim == 0:
            emb.dim = len(emb.embed("ping")))  # auto-détection dimension
        else:
            emb.dim = cfg.dim
        return emb

    def embed(self, text: str) -> List[float]:
        res = self.client.embeddings.create(model=self.cfg.model, input=text)
        return list(res.data[0].embedding)

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        res = self.client.embeddings.create(model=self.cfg.model, input=list(texts))
        return [list(r.embedding) for r in res.data]
