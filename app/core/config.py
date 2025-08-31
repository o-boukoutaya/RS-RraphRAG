# app/core/config.py
# Core → config (YAML + env + cache)
from __future__ import annotations
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, replace


import yaml
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Pydantic models (typage fort + auto-doc)
# ---------------------------------------------------------------------------

# Configuration de l'application
class AppCfg(BaseModel):
    name: str = "rs-rraPhrag"
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8050
    port_snd: int = 8443
    log_level: str = "INFO"
    # dev_reload: bool = True

# Configuration du stockage
class StorageCfg(BaseModel):
    root: Path = Path("./data")
    tmp_dir: Path = Path("./data/_tmp")
    series_dirname: str = "series"
    allowed_extensions: List[str] = Field(default_factory=lambda: [
    ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".xls"
    ])
    max_file_size_mb: int = 64

# Configuration de la base de données Neo4j
# @dataclass(frozen=True)
class Neo4jCfg(BaseModel):
    uri: str = "bolt://localhost:7687"
    database: str = "neo4j"
    username: str = "neo4j"
    password: str = "neo4j"
    connection_timeout: float = 15.0
    max_connection_lifetime: int = 3600
    max_transaction_retry_time: float = 10.0

# Configuration de l'upload
# class UploadCfg(BaseModel):
#     max_size_mb: int = 50

# Configuration du stockage vectoriel chroma DB
class VectorChromaCfg(BaseModel):
    persist_dir: Path = Path("./chroma")

# Configuration du stockage vectoriel
class VectorCfg(BaseModel):
    provider: str = "chroma"
    chroma: VectorChromaCfg = VectorChromaCfg()
    type: str = "memory"

# Configuration de l'API OpenAI
class OpenAICfg(BaseModel):
    api_key: Optional[str] = None
#     api_base: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-ada-002"

# Configuration de l'API Azure OpenAI
class AzureOpenAICfg(BaseModel):
    api_key: Optional[str] = None
    api_version: str = "2023-07-01-preview"
    azure_endpoint: Optional[str] = None # https://openai4orange.openai.azure.com
    dep_name: Optional[str] = None # "4Orange"
    embed_dep: Optional[str] = "text-embedding-ada-002"

# Configuration de l'API Gemini
class GeminiCfg(BaseModel):
    api_key: Optional[str] = None
    chat_model: str = "gemini-1.5-pro"
    embed_model: str = "text-embedding-004"

# Configuration du LLM provider
class ProviderCfg(BaseModel):
    openai : OpenAICfg = OpenAICfg()
    azure: AzureOpenAICfg = AzureOpenAICfg()
    gemini: GeminiCfg = GeminiCfg()
    default: str = "azure" # openai | azure | gemini

# Configuration de l'OCR
class OcrCfg(BaseModel):
    enabled: bool = False
    provider: str = "tesseract"
    languages: List[str] = Field(default_factory=lambda: ["eng", "fra", "ara"])
    tesseract_cmd: Optional[str] = None
    tessdata_prefix: Optional[str] = None

# Configuration du découpage
class ChunkCfg(BaseModel):
    strategy: str = "simple"
    size: int = 800
    overlap: int = 150


# # Configuration des embeddings
# class EmbeddingCfg(BaseModel):
#     dim: int = 1536

# Configuration des pipelines
class PipelinesCfg(BaseModel):
    end_to_end: Dict[str, List[str]] | Dict[str, Any] | None = None

# Configuration générale
class Settings(BaseModel):
    app: AppCfg = AppCfg()
    storage: StorageCfg = StorageCfg()
    neo4j: Neo4jCfg = Neo4jCfg()
    vector: VectorCfg = VectorCfg()
    provider: ProviderCfg = ProviderCfg()
    ocr: OcrCfg = OcrCfg()
    chunk: ChunkCfg = ChunkCfg()
    pipelines: PipelinesCfg = PipelinesCfg()



# ---------------------------------------------------------------------------
# YAML loader + interpolation ${VAR:default}
# ---------------------------------------------------------------------------

# Pattern pour l'expansion des variables d'environnement
_env_pattern = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")

# Fonction d'interpolation des variables d'environnement
def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            var, default = match.group(1), match.group(2) or ""
            return os.getenv(var, default)
        return _env_pattern.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value

# Fonction de chargement des fichiers YAML
def _load_yaml(path: Path) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw

# ---------------------------------------------------------------------------
# Public factory (cache)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)  # Cache pour éviter de recharger à chaque appel
# get_settings : renvoie les paramètres de configuration
def get_settings() -> Settings:
    """Charge .env puis settings.yaml, effectue l'interpolation et valide."""
    load_dotenv(override=True)

    cfg_path = Path("config/settings.yaml")
    data = _load_yaml(cfg_path)
    data = _interpolate_env(data)

    try:
        return Settings(**data)
    except ValidationError as exc:
        # Affiche l'erreur proprement dès le boot
        raise RuntimeError(f"Invalid configuration in {cfg_path}:\n{exc}")


# Fonction de validation des paramètres
# def validate_settings(settings):
#     p = settings.llm.provider
#     missing = []
#     if p == "openai":
#         for k in ["api_key", "base_url", "chat_model", "embed_model"]:
#             if not getattr(settings.llm.openai, k, None):
#                 missing.append(f"llm.openai.{k}")
#     elif p == "azure":
#         for k in ["api_key", "endpoint", "api_version", "chat_deployment", "embed_deployment"]:
#             if not getattr(settings.llm.azure, k, None):
#                 missing.append(f"llm.azure.{k}")
#     elif p == "gemini":
#         for k in ["api_key", "chat_model", "embed_model"]:
#             if not getattr(settings.llm.gemini, k, None):
#                 missing.append(f"llm.gemini.{k}")
#     if missing:
#         raise RuntimeError(f"Invalid settings for provider={p}: missing {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
"Settings",
"get_settings",
]