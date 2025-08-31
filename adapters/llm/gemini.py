# adapters/llm/gemini.py
from __future__ import annotations
from typing import List, Sequence, Optional, Dict
from dataclasses import dataclass
from ast import If
from app.core.config import get_settings, ProviderCfg
import logging, openai, os
from adapters.llm.base import Provider, _get_env

# Imports protégés (pas d'erreur si non installés)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
except Exception as e:  # pragma: no cover
    ChatGoogleGenerativeAI = None  # type: ignore
    GoogleGenerativeAIEmbeddings = None  # type: ignore

try:
    # Optionnel : ping modèle (métadonnées) via client officiel
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

log = logging.getLogger(__name__)


@dataclass
class GeminiProvider(Provider):
    """
    Provider Gemini:
    - Chat : ChatGoogleGenerativeAI (model p.ex. "gemini-1.5-pro")
    - Embeddings : GoogleGenerativeAIEmbeddings (model p.ex. "text-embedding-004")
    """
    chat_model: str = "gemini-1.5-pro"
    embed_model: str = "text-embedding-004"
    api_key: Optional[str] = None
    _chat = None
    _emb = None

    def __init__(self):
        self.gemini = get_settings().provider.gemini
        # Fallback env si pas fournis
        self.api_key = self.gemini.api_key  or _get_env("GOOGLE_API_KEY")
        self.chat_model = self.gemini.chat_model
        self.embed_model = self.gemini.embed_model

        if ChatGoogleGenerativeAI is None or GoogleGenerativeAIEmbeddings is None:
            raise RuntimeError(
                "Gemini provider requires 'langchain-google-genai' and 'google-generativeai'. "
                "pip install -U langchain-google-genai google-generativeai"
            )
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY is missing for GeminiProvider.")
        if not self.chat_model:
            raise RuntimeError("GOOGLE_CHAT_MODEL is missing for GeminiProvider.")
        if not self.embed_model:
            raise RuntimeError("GOOGLE_EMBED_MODEL is missing for GeminiProvider.")

        # Instancie chat (ex: "gemini-1.5-pro" ou "gemini-1.5-flash")
        self._chat = ChatGoogleGenerativeAI(
            model=self.chat_model,
            google_api_key=self.api_key,
            temperature=0,
            max_output_tokens=None,
        )

        # Instancie embeddings (ex: "text-embedding-004")
        self._emb = GoogleGenerativeAIEmbeddings(
            model=self.embed_model,
            google_api_key=self.api_key,
            # dimensions=self.gemini.dim
        )

        # Configure client officiel (facultatif) pour introspection
        if genai:
            try:
                genai.configure(api_key=self.api_key)
            except Exception:
                pass

        
    # ---- Embeddings ----
    def embed(self, text: str, *, dimensions: Optional[int] = None) -> List[float]:
        # GoogleGenerativeAIEmbeddings n'expose pas de 'dimensions' paramétrable.
        try:
            return self._emb.embed_query(text)  # type: ignore[union-attr]
        except Exception as e:
            log.error(f"Error in embed: {e} + Module used {self._emb.__class__.__name__} + model {self.embed_model}")
            return []

    def embed_batch(self, texts: Sequence[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        try:
            return self._emb.embed_documents(list(texts))  # type: ignore[union-attr]
        except Exception as e:
            log.error(f"Error in embed_batch: {e} + Module used {self._emb.__class__.__name__} + model {self.embed_model}")
            return []

    def embed_texts(self, texts: List[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        return self.embed_batch(texts, dimensions=dimensions)
    
    # ---- Chat ----
    def ask_llm(self, query: str) -> str:
        resp = self._chat.invoke(query)  # type: ignore[union-attr]
        return getattr(resp, "content", str(resp))
    
    def capabilities(self) -> Dict:
        dims = None
        try:
            # petit ping (peut consommer un appel) — ne pas appeler en prod si inutile
            v = self.embed("ping")
            dims = len(v)
        except Exception:
            pass
        return {
            "provider": "gemini",
            "supports_chat": True,
            "supports_embeddings": True,
            "chat_model": self.chat_model,
            "embed_model": self.embed_model,
            "dims": dims,
        }