# adapters/llm/openai_azure.py
from __future__ import annotations
from typing import List, Sequence, Optional, Dict
from dataclasses import dataclass
from app.core.config import get_settings
import logging

from adapters.llm.base import Provider, _get_env, batch_iter

# SDK OpenAI 1.x
try:
    from openai import AzureOpenAI  # type: ignore
except Exception as e:  # pragma: no cover
    AzureOpenAI = None  # type: ignore

log = logging.getLogger(__name__)


@dataclass
class AzureOpenAIProvider(Provider):
    """
    Provider Azure OpenAI (OpenAI SDK 1.x):
    - Chat: chat.completions (déploiement GPT-4/4o)
    - Embeddings: embeddings.create (déploiement text-embedding-3-*)
    """
    azure_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    api_key: Optional[str] = None

    chat_dep: Optional[str] = None  # ex: "4Orange" (déploiement chat)
    embed_dep: Optional[str] = None  # ex: "text-embedding-3-small" (déploiement embeddings)
    default_embed_dims: Optional[int] = 1536  # ex: 1536

    max_batch: int = 512

    _client = None

    def __post_init__(self):
        self.azure = get_settings().provider.azure
        if AzureOpenAI is None:
            raise RuntimeError("Azure OpenAI SDK not installed. pip install openai>=1.0.0")

        # Fallback ENV si non fournis
        self.azure_endpoint = self.azure_endpoint or self.azure.azure_endpoint
        self.api_version = self.api_version or self.azure.api_version
        self.api_key = self.api_key or self.azure.api_key

        # Déploiements
        self.chat_dep = self.chat_dep or self.azure.dep_name
        self.embed_dep = self.embed_dep or self.azure.embed_dep
        try:
            self.default_embed_dims = int(self.default_embed_dims or self.azure.dim or 0) or None
        except Exception:
            self.default_embed_dims = None

        if not self.azure_endpoint or not self.api_version or not self.api_key:
            raise RuntimeError("Azure endpoint/version/key are required (OPENAI_API_BASE, OPENAI_API_VERSION, AZURE_OPENAI_API_KEY).")

        # Client
        self._client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.azure_endpoint,
        )

        # Chat déployé ?
        if not self.chat_dep:
            log.warning("AzureOpenAIProvider: chat_dep is not set. ask_llm() will fail until configured.")

        # Embeddings déployé ?
        if not self.embed_dep:
            log.warning("AzureOpenAIProvider: embed_dep is not set. embed*() will raise NotImplementedError until configured.")

    # ---- Embeddings ----
    def embed(self, text: str, *, dimensions: Optional[int] = None) -> List[float]:
        if not self.embed_dep:
            raise NotImplementedError("Azure embeddings not configured (embed_dep empty). Configure AZURE_EMBED_DEP / DEPLOYMENT_NAME_EMBED.")
        dims = dimensions or self.default_embed_dims
        res = self._client.embeddings.create(  # type: ignore[union-attr]
            model=self.embed_dep,  # deployment name (NOT model name)
            input=text,
            **({"dimensions": dims} if dims else {}),
        )
        return list(res.data[0].embedding)

    def embed_batch(self, texts: Sequence[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        if not self.embed_dep:
            raise NotImplementedError("Azure embeddings not configured (embed_dep empty). Configure AZURE_EMBED_DEP / DEPLOYMENT_NAME_EMBED.")
        dims = dimensions or self.default_embed_dims
        out: List[List[float]] = []
        for chunk in batch_iter(list(texts), self.max_batch):
            res = self._client.embeddings.create(  # type: ignore[union-attr]
                model=self.embed_dep,
                input=list(chunk),
                **({"dimensions": dims} if dims else {}),
            )
            out.extend([list(d.embedding) for d in res.data])
        return out

    # ---- Chat ----
    def ask_llm(self, query: str) -> str:
        if not self.chat_dep:
            raise RuntimeError("Azure chat deployment not configured (chat_dep empty). Configure DEPLOYMENT_NAME_CHAT / DEPLOYMENT_NAME.")
        resp = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=self.chat_dep,  # deployment name
            messages=[{"role": "user", "content": query}],
            temperature=0,
        )
        return resp.choices[0].message.content or ""

    def capabilities(self) -> Dict:
        return {
            "provider": "azure-openai",
            "supports_chat": bool(self.chat_dep),
            "supports_embeddings": bool(self.embed_dep),
            "chat_dep": self.chat_dep,
            "embed_dep": self.embed_dep,
            "default_embed_dims": self.default_embed_dims,
        }
