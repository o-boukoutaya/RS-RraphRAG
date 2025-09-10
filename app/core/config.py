# app/core/config.py
# Core → config (YAML + env + cache)
from __future__ import annotations
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, replace
from .config_kg_models import AppKgCfg


import yaml
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Pydantic models (typage fort + auto-doc)
# ---------------------------------------------------------------------------

class AppCfg(BaseModel):
    """Configuration de l'application"""
    name: str = "rs-rraPhrag"
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8050
    port_snd: int = 8443
    log_level: str = "INFO"
    transport: str = "sse" # http | stdio | sse
    kg_app: AppKgCfg = AppKgCfg()
    # dev_reload: bool = True

class StorageCfg(BaseModel):
    """Configuration du stockage des fichiers"""
    root: Path = Path("./data")
    tmp_dir: Path = Path("./data/_tmp")
    series_dirname: str = "series"
    allowed_extensions: List[str] = Field(default_factory=lambda: [
    ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".xls"
    ])
    max_file_size_mb: int = 64

class Neo4jCfg(BaseModel):
    """Configuration de la base de données Neo4j"""
    uri: str = "bolt://localhost:7687"
    database: str = "neo4j"
    username: str = "neo4j"
    password: str = "neo4j"
    connection_timeout: float = 15.0
    max_connection_lifetime: int = 3600
    max_transaction_retry_time: float = 10.0

class VectorChromaCfg(BaseModel):
    """Configuration du stockage vectoriel ChromaDB"""
    persist_dir: Path = Path("./chroma")

class VectorCfg(BaseModel):
    """Configuration du stockage vectoriel"""
    provider: str = "chroma"
    chroma: VectorChromaCfg = VectorChromaCfg()
    type: str = "memory"

class OpenAICfg(BaseModel):
    """Configuration de l'API OpenAI"""
    api_key: Optional[str] = None
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-ada-002"

class AzureOpenAICfg(BaseModel):
    """Configuration de l'API Azure OpenAI"""
    api_key: Optional[str] = None
    api_version: str = "2023-07-01-preview"
    azure_endpoint: Optional[str] = None # https://openai4orange.openai.azure.com
    dep_name: Optional[str] = None # "4Orange"
    embed_dep: Optional[str] = "text-embedding-ada-002"

class GeminiCfg(BaseModel):
    """Configuration de l'API Gemini"""
    api_key: Optional[str] = None
    chat_model: str = "gemini-1.5-pro"
    embed_model: str = "text-embedding-004"

class ProviderCfg(BaseModel):
    """Configuration du LLM provider"""
    openai : OpenAICfg = OpenAICfg()
    azure: AzureOpenAICfg = AzureOpenAICfg()
    gemini: GeminiCfg = GeminiCfg()
    default: str = "azure" # openai | azure | gemini

class OcrCfg(BaseModel):
    """Configuration de l'OCR"""
    enabled: bool = False
    provider: str = "tesseract"
    languages: List[str] = Field(default_factory=lambda: ["eng", "fra", "ara"])
    tesseract_cmd: Optional[str] = None
    tessdata_prefix: Optional[str] = None

class ChunkCfg(BaseModel):
    """Configuration du découpage des documents"""
    strategy: str = "simple"
    size: int = 800
    overlap: int = 150


class PipelinesCfg(BaseModel):
    """Configuration des pipelines"""
    end_to_end: Dict[str, List[str]] | Dict[str, Any] | None = None

class Settings(BaseModel):
    """Configuration générale de l'application"""
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

def _interpolate_env(value: Any) -> Any:
    """Interpole les variables d'environnement dans les chaînes de caractères."""
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

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Charge un fichier YAML et retourne un dictionnaire."""
    if not os.path.exists(path):
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw

# ---------------------------------------------------------------------------
# Public factory (cache)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Charge .env puis settings.yaml, effectue l'interpolation et valide (renvoie les paramètres de configuration)."""
    load_dotenv(override=True)

    cfg_path = Path("config/settings.yaml")
    graph_cfg_path = Path("config/graph_based.yaml")
    data = _load_yaml(cfg_path)
    data_graph = _load_yaml(graph_cfg_path)
    # Fusionner les deux configurations
    data = {**data, **data_graph}
    data = _interpolate_env(data)

    try:
        return Settings(**data)
    except ValidationError as exc:
        # Affiche l'erreur proprement dès le boot
        raise RuntimeError(f"Invalid configuration in {cfg_path}:\n{exc}")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
"Settings",
"get_settings",
]