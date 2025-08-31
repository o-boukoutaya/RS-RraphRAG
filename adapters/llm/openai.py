# adapters/llm/openai.py
from __future__ import annotations
from typing import List, Sequence, Optional, Dict
from dataclasses import dataclass
from app.core.config import get_settings
import logging

from adapters.llm.base import Provider, _get_env, batch_iter

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

log = logging.getLogger(__name__)


@dataclass
class OpenAIProvider(Provider):
    """
    Provider OpenAI direct (OpenAI SDK 1.x):
    - Chat: chat.completions (ex: "gpt-4o-mini")
    - Embeddings: embeddings.create (ex: "text-embedding-3-small")
    """
    api_key: Optional[str] = None
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    default_embed_dims: Optional[int] = None
    max_batch: int = 512

    _client = None

    def __post_init__(self):
        self.openai = get_settings().provider.openai
        if OpenAI is None:
            raise RuntimeError("OpenAI SDK not installed. pip install openai>=1.0.0")
        self.api_key = self.api_key or self.openai.api_key
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIProvider.")
        try:
            self.default_embed_dims = int(self.default_embed_dims or self.openai.dim or 0) or None
        except Exception:
            self.default_embed_dims = None

        self._client = OpenAI(api_key=self.api_key)

    # ---- Embeddings ----
    def embed(self, text: str, *, dimensions: Optional[int] = None) -> List[float]:
        dims = dimensions or self.default_embed_dims
        res = self._client.embeddings.create(  # type: ignore[union-attr]
            model=self.embed_model,
            input=text,
            **({"dimensions": dims} if dims else {}),
        )
        return list(res.data[0].embedding)

    def embed_batch(self, texts: Sequence[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        dims = dimensions or self.default_embed_dims
        out: List[List[float]] = []
        for chunk in batch_iter(list(texts), self.max_batch):
            res = self._client.embeddings.create(  # type: ignore[union-attr]
                model=self.embed_model,
                input=list(chunk),
                **({"dimensions": dims} if dims else {}),
            )
            out.extend([list(d.embedding) for d in res.data])
        return out

    # ---- Chat ----
    def ask_llm(self, query: str) -> str:
        resp = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=self.chat_model,
            messages=[{"role": "user", "content": query}],
            temperature=0,
        )
        return resp.choices[0].message.content or ""

    def capabilities(self) -> Dict:
        return {
            "provider": "openai",
            "supports_chat": True,
            "supports_embeddings": True,
            "chat_model": self.chat_model,
            "embed_model": self.embed_model,
            "default_embed_dims": self.default_embed_dims,
        }
