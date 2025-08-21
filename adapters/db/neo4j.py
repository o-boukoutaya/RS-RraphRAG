# adapters/db/neo4j.py
from neo4j import GraphDatabase
from app.core.config import get_settings

class Neo4jClient:
    def __init__(self):
        s = get_settings().neo4j
        self.driver = GraphDatabase.driver(s.uri, auth=(s.username, s.password))

    def close(self):
        self.driver.close()
