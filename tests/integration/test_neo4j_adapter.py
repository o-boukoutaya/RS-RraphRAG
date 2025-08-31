# tests/integration/test_neo4j_adapter.py
import os, pytest
from adapters.db.neo4j import Neo4jAdapter

requires_neo4j = pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="NEO4J_* env vars not set"
)

@requires_neo4j
def test_vector_index_and_query():
    db = Neo4jAdapter(uri=os.getenv("NEO4J_URI"),
                      user=os.getenv("NEO4J_USER"),
                      password=os.getenv("NEO4J_PASSWORD"),
                      database=os.getenv("NEO4J_DATABASE", None))
    idx = "chunkIndex__test"
    if not db.check_index_exists(idx):
        db.create_vector_index(idx, label="Chunk", prop="embedding", dimensions=4, similarity="cosine")

    rows = [
        {"cid":"t:1","text":"alpha","vec":[0.1,0.2,0.3,0.4],"series":"t","file":"f","page":1,"order":0,"provider":"fake","model":"fake","dims":4,"ts":0},
        {"cid":"t:2","text":"beta","vec":[0.2,0.1,0.3,0.1],"series":"t","file":"f","page":1,"order":1,"provider":"fake","model":"fake","dims":4,"ts":0},
    ]
    assert db.upsert_chunks(rows, label="Chunk", prop="embedding") == 2

    hits = db.query_top_k(idx, [0.09,0.19,0.29,0.41], k=1, series="t")
    assert hits and "score" in hits[0]
    db.close()