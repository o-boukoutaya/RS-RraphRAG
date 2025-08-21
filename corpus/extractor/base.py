# corpus/extractor/base.py
from abc import ABC, abstractmethod
from typing import Iterable, List
from corpus.models import Document, TextBlock

class BaseExtractor(ABC):
    extensions: Iterable[str] = ()

    @abstractmethod
    def extract(self, doc: Document) -> List[TextBlock]: ...
