# Ressources singletons (branchement centralisé des adapters) :
# Ajoute un petit module d’injection de dépendances que le code métier peut consommer.

from functools import lru_cache
from pathlib import Path
from adapters.llm.openai import OpenAIProvider
from adapters.llm.phi import PhiLocalProvider
from app.core.config import get_settings
from typing import List, Optional

from adapters.vector.base import InMemoryIndex
from adapters.db.neo4j import Neo4jAdapter, client_from_settings
from adapters.storage.local import LocalStorage
from adapters.llm.openai_azure import AzureOpenAIProvider
from adapters.llm.gemini import GeminiProvider


@lru_cache
def get_neo4j_settings():
    return client_from_settings()

@lru_cache
def get_db():
    return Neo4jAdapter()

@lru_cache
def test_cnx():
    from adapters.db.neo4j import Neo4jAdapter
    db = Neo4jAdapter()
    return db.ping()

@lru_cache
def get_all_settings():
    return get_settings()

@lru_cache
def get_provider():
    """ Returns instance from Provider of default (if available). """
    match get_settings().provider.default:
        case "azure":
            provider = AzureOpenAIProvider()
        case "gemini":
            provider = GeminiProvider()
        case "openai":
            provider = OpenAIProvider()
        case "phi-local":
            provider = PhiLocalProvider()
    return provider

@lru_cache
def ask_llm(query: str):
    provider = get_provider()
    resp =  provider.ask_llm(query)
    return {"response": resp, "provider": provider.__class__.__name__}


@lru_cache
def get_storage():
    # lisez la racine depuis votre config actuelle
    return LocalStorage()

@lru_cache
def get_all_series() -> List[str]:
    """ Retourner la liste des séries sous data/series"""
    series_dir = Path("data/series")
    return [d.name for d in series_dir.iterdir() if d.is_dir()]

@lru_cache
def sanity_check_gemini_ask() -> str:
    from adapters.llm.gemini import GeminiProvider
    g = GeminiProvider()  # GOOGLE_API_KEY requis
    return g.ask_llm("Ping")[:30]

@lru_cache
def sanity_check_gemini_embd() -> int:
    from adapters.llm.gemini import GeminiProvider
    g = GeminiProvider()  # GOOGLE_API_KEY requis
    return len(g.embed("hello"))

@lru_cache
def sanity_check_azure_ask() -> str:
    # AZURE (chat uniquement, pas d'embeddings tant que AZURE_EMBED_DEP est vide)
    from adapters.llm.openai_azure import AzureOpenAIProvider
    a = AzureOpenAIProvider()
    return a.ask_llm("2+2=?")

@lru_cache
def sanity_check_phi_ask() -> str:
    # PHI local (si libs et poids dispos)
    from adapters.llm.phi import PhiLocalProvider
    p = PhiLocalProvider()
    return p.ask_llm("Say hi")[:80]

@lru_cache
def sanity_check_phi_embd() -> int:
    # PHI local (si libs et poids dispos)
    from adapters.llm.phi import PhiLocalProvider
    p = PhiLocalProvider()
    return len(p.embed("hello"))
