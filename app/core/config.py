# app/core/config.py
# Core → config (YAML + env + cache)
from __future__ import annotations
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    log_level: str = "INFO"

# Configuration du stockage
class StorageCfg(BaseModel):
    root: Path = Path("./data")
    series_dirname: str = "series"
    root: Path = Path("./data")
    series_dirname: str = "series"
    tmp_dir: Path = Path("./data/_tmp")
    allowed_extensions: List[str] = Field(default_factory=lambda: [
    ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".xls"
    ])

# Configuration de l'upload
class UploadCfg(BaseModel):
    max_size_mb: int = 50

# Configuration de l'OCR
class OcrCfg(BaseModel):
    enabled: bool = False
    provider: str = "tesseract"
    languages: List[str] = Field(default_factory=lambda: ["eng", "fra", "ara"])
    tesseract_cmd: Optional[str] = None

# Configuration de l'API OpenAI
class OpenAICfg(BaseModel):
    api_key: Optional[str] = None
    api_base: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"

# Configuration de l'API Azure OpenAI
class AzureOpenAICfg(BaseModel):
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    api_version: str = "2024-06-01"
    chat_deployment: str = "gpt-4o-mini"
    embed_deployment: str = "text-embedding-3-small"

# Configuration du modèle de langage
class LLMCfg(BaseModel):
    provider: str = "openai" # openai | azure
    openai: OpenAICfg = OpenAICfg()
    azure: AzureOpenAICfg = AzureOpenAICfg()

# Configuration de la base de données Neo4j
class Neo4jCfg(BaseModel):
    uri: str = "bolt://localhost:7687"
    database: str = "neo4j"
    username: str = "neo4j"
    password: str = "neo4j"

# Configuration du stockage vectoriel chroma DB
class VectorChromaCfg(BaseModel):
    persist_dir: Path = Path("./chroma")

# Configuration du stockage vectoriel
class VectorCfg(BaseModel):
    provider: str = "chroma"
    chroma: VectorChromaCfg = VectorChromaCfg()

# Configuration des embeddings
class EmbeddingCfg(BaseModel):
    dim: int = 1536

# Configuration du découpage
class ChunkCfg(BaseModel):
    strategy: str = "simple"
    size: int = 800
    overlap: int = 150

# Configuration des pipelines
class PipelinesCfg(BaseModel):
    end_to_end: Dict[str, List[str]] | Dict[str, Any] | None = None

# Configuration générale
class Settings(BaseModel):
    app: AppCfg = AppCfg()
    storage: StorageCfg = StorageCfg()
    upload: UploadCfg = UploadCfg()
    ocr: OcrCfg = OcrCfg()
    llm: LLMCfg = LLMCfg()
    neo4j: Neo4jCfg = Neo4jCfg()
    vector: VectorCfg = VectorCfg()
    embedding: EmbeddingCfg = EmbeddingCfg()
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
"Settings",
"get_settings",
]