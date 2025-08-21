# adapters/llm/openai_azure.py
from typing import List
from app.core.config import get_settings
from openai import AzureOpenAI

class AzureOpenAIEmbedder:
    def __init__(self):
        cfg = get_settings().llm
        p = cfg.params
        self.client = AzureOpenAI(api_key=p["api_key"], api_version=p["api_version"], azure_endpoint=p["api_base"])
        self.deployment = p.get("embedding_deployment")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        res = self.client.embeddings.create(model=self.deployment, input=texts)
        return [d.embedding for d in res.data]
