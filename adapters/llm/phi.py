# adapters/llm/phi.py
from __future__ import annotations
from typing import List, Sequence, Optional, Dict
from dataclasses import dataclass
import logging
import os

from adapters.llm.base import Provider, _get_env, batch_iter

# Imports protégés
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM  # type: ignore
except Exception:
    pipeline = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None  # type: ignore

log = logging.getLogger(__name__)


@dataclass
class PhiLocalProvider(Provider):
    """
    Provider local:
    - Chat LLM : transformers (ex: microsoft/Phi-3.5-mini-instruct)
    - Embeddings : sentence-transformers (ex: all-MiniLM-L6-v2, 384 dims)
    NOTE: Télécharge les modèles au premier run (réseau requis). Utilise CPU par défaut.
    """
    chat_model_name: Optional[str] = "microsoft/Phi-3.5-mini-instruct"
    embed_model_name: Optional[str] = "all-MiniLM-L6-v2"
    device: Optional[str] = "cpu"          # "cuda", "mps", "cpu" (None => auto)
    max_new_tokens: int = 512
    temperature: float = 0.2
    batch_size: int = 256

    _chat_pipe = None
    _emb_model = None

    def __post_init__(self):
        # Defaults (env override)
        self.chat_model_name = self.chat_model_name or _get_env("PHI_MODEL_NAME", "microsoft/Phi-3.5-mini-instruct")
        self.embed_model_name = self.embed_model_name or _get_env("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
        self.device = self.device or _get_env("HF_DEVICE")  # e.g., "cuda", "mps", "cpu"

        # Check dependencies
        if pipeline is None or AutoTokenizer is None or AutoModelForCausalLM is None:
            raise RuntimeError("Transformers not installed. pip install transformers accelerate")
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers not installed. pip install sentence-transformers")

        # Chat pipeline
        try:
            self._chat_pipe = pipeline(
                "text-generation",
                model=self.chat_model_name,
                # BitsAndBytes / device_map auto si accelerate présent
                device_map="auto" if self.device is None else None,
                device=self.device if self.device else None,
                trust_remote_code=True,
            )
        except Exception as e:
            raise RuntimeError(f"Unable to load PHI chat model '{self.chat_model_name}': {e}")

        # Embedding model
        try:
            self._emb_model = SentenceTransformer(self.embed_model_name)
        except Exception as e:
            raise RuntimeError(f"Unable to load sentence-transformers model '{self.embed_model_name}': {e}")

    # ---- Embeddings ----
    def embed(self, text: str, *, dimensions: Optional[int] = None) -> List[float]:
        vec = self._emb_model.encode([text], normalize_embeddings=True)[0]  # type: ignore[union-attr]
        return vec.astype(float).tolist()

    def embed_batch(self, texts: Sequence[str], *, dimensions: Optional[int] = None) -> List[List[float]]:
        out: List[List[float]] = []
        for chunk in batch_iter(list(texts), self.batch_size):
            mat = self._emb_model.encode(list(chunk), normalize_embeddings=True)  # type: ignore[union-attr]
            out.extend([row.astype(float).tolist() for row in mat])
        return out

    # ---- Chat ----
    def _build_prompt(self, user_msg: str) -> str:
        # Prompt simple compatible Phi Instruct
        return (
            "<|system|>\nYou are a helpful AI assistant.\n"
            "<|user|>\n" + user_msg.strip() + "\n"
            "<|assistant|>\n"
        )

    def ask_llm(self, query: str) -> str:
        prompt = self._build_prompt(query)
        try:
            gen = self._chat_pipe(
                prompt,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                pad_token_id=0,
                eos_token_id=self._chat_pipe.tokenizer.eos_token_id,  # type: ignore[attr-defined]
                num_return_sequences=1,
            )
            text = gen[0]["generated_text"]
            # On enlève le prompt initial si renvoyé tel quel
            if text.startswith(prompt):
                text = text[len(prompt):]
            return text.strip()
        except Exception as e:
            raise RuntimeError(f"PHI ask_llm failed: {e}")

    def capabilities(self) -> Dict:
        dim = None
        try:
            dim = len(self.embed("ping"))
        except Exception:
            pass
        return {
            "provider": "phi-local",
            "supports_chat": True,
            "supports_embeddings": True,
            "chat_model": self.chat_model_name,
            "embed_model": self.embed_model_name,
            "dims": dim,
        }
