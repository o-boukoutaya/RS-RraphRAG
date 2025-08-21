from app.core.config import get_settings
from adapters.db.neo4j import client_from_settings
from adapters.llm.openai_azure import AzureOpenAIEmbedder
from adapters.vector.base import InMemoryIndex
from adapters.storage.local import LocalStorage
import io

# Neo4j
def test_neo4j_connection():
    db = client_from_settings(get_settings())
    assert db.ping()
    with db.session(readonly=True) as s:
        rows = list(s.run("RETURN 1 AS ok"))

# Storage (en parallèle de corpus.storage)
def test_create_local_storage(tmp_path):
    st = LocalStorage.from_settings(get_settings())
    sid = st.create_series()     # auto
    p = st.save_stream(sid, "demo.txt", io.BytesIO(b"hello"))

# Embedder + Vector
def test_embedder():
    emb = AzureOpenAIEmbedder.from_settings(get_settings())
    idx = InMemoryIndex(dim=emb.dim)
    v = emb.embed("bonjour")
    idx.add(["a1"], [v], [{"text":"bonjour"}])
    hits = idx.search(v, k=1)
