# corpus/extractor/registry.py
from typing import Dict, Type
from .base import BaseExtractor

_REGISTRY: Dict[str, Type[BaseExtractor]] = {}

def register(ext: str):
    def deco(cls: Type[BaseExtractor]):
        _REGISTRY[ext.lower()] = cls
        return cls
    return deco

def get(ext: str) -> Type[BaseExtractor] | None:
    return _REGISTRY.get(ext.lower())
