# app/core/config.py
# Core → config (YAML + env + cache)
from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
import os, yaml

ROOT = Path(__file__).resolve().parents[2]
CFG_DIR = ROOT / "config"
SETTINGS_FILE = CFG_DIR / "settings.yaml"

def _env_expand(obj):
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    if isinstance(obj, list):
        return [_env_expand(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _env_expand(v) for k, v in obj.items()}
    return obj

@dataclass
class StorageCfg:
    backend: str = "local"
    root_dir: str = "data"
    tmp_dir: str = "data/_tmp"
    allowed_extensions: List[str] = field(default_factory=lambda: [".pdf",".txt",".csv",".docx",".xlsx",".xls"])

@dataclass
class Neo4jCfg:
    uri: str = "bolt://localhost:7687"
    database: str = "neo4j"
    username: str = "neo4j"
    password: str = ""

@dataclass
class VectorCfg:
    provider: str = "chroma"
    params: Dict[str, str] = field(default_factory=dict)

@dataclass
class LlmCfg:
    provider: str = "openai.azure"
    embedding_model: str = "text-embedding-3-large"
    chat_model: str = "gpt-4o-mini"
    params: Dict[str, str] = field(default_factory=dict)

@dataclass
class OcrCfg:
    enabled: bool = True
    engine: str = "tesseract"           # ou "rapidocr"
    languages: List[str] = field(default_factory=lambda: ["eng","fra","ara"])
    min_confidence: float = 0.4

@dataclass
class ChunkCfg:
    strategy: str = "tokens"
    tokens: int = 600
    overlap: int = 80
    normalize_whitespace: bool = True

@dataclass
class Settings:
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8050
    dev_reload: bool = True
    storage: StorageCfg = field(default_factory=StorageCfg)
    neo4j: Neo4jCfg = field(default_factory=Neo4jCfg)
    vector: VectorCfg = field(default_factory=VectorCfg)
    llm: LlmCfg = field(default_factory=LlmCfg)
    ocr: OcrCfg = field(default_factory=OcrCfg)
    chunking: ChunkCfg = field(default_factory=ChunkCfg)

# Core/config : get_settings() lit YAML + ${ENV}, renvoie des dataclasses typées → cohérent et flexible.
@lru_cache()
def get_settings() -> Settings:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw = _env_expand(raw)                # remplace ${VARS} par os.environ
    # merge simple (tu peux raffiner si besoin)
    s = Settings(
        env=raw.get("app",{}).get("env","dev"),
        host=raw.get("app",{}).get("host","127.0.0.1"),
        port=int(raw.get("app",{}).get("port",8050)),
        dev_reload=bool(raw.get("app",{}).get("dev_reload", True)),
        storage=StorageCfg(**raw.get("storage",{})),
        neo4j=Neo4jCfg(**raw.get("neo4j",{})),
        vector=VectorCfg(**raw.get("vector",{})),
        llm=LlmCfg(**raw.get("llm",{})),
        ocr=OcrCfg(**raw.get("ocr",{})),
        chunking=ChunkCfg(**raw.get("chunking",{})),
    )
    return s
