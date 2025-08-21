# adapters/db/neo4j.py
# db/neo4j : sélecteur de DB, timeouts, with + session() + ping(), gestion d’exceptions.
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Optional, Iterable, Any, Dict
import logging, contextlib

from app.core.config import get_settings
from neo4j import GraphDatabase, READ_ACCESS, WRITE_ACCESS
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

log = logging.getLogger("neo4j")

@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"
    connection_timeout: float = 15.0
    max_connection_lifetime: int = 3600
    max_transaction_retry_time: float = 10.0


# Client Neo4j
class Neo4jClient:
    """Client prêt à l'emploi : with Neo4jClient(cfg) as db: ..."""

    def __init__(self, cfg: Neo4jConfig):
        # s = get_settings().neo4j
        # self.driver = GraphDatabase.driver(s.uri, auth=(s.username, s.password))
        self.cfg = cfg
        self._driver = GraphDatabase.driver(
            cfg.uri,
            auth=(cfg.username, cfg.password),
            connection_timeout=cfg.connection_timeout,
            max_connection_lifetime=cfg.max_connection_lifetime,
            max_transaction_retry_time=cfg.max_transaction_retry_time,
        )

    def __enter__(self) -> "Neo4jClient": return self    
    def __exit__(self, *_): self.close()
    def close(self): 
        if self._driver: self._driver.close()

    # Changement de base de données ⇒ .using("autre_db") sélecteur de base simple.
    def using(self, database: Optional[str]) -> "Neo4jClient":
        """Retourne un client pointant sur une autre DB sans toucher l’original."""
        if not database or database == self.cfg.database: return self
        return Neo4jClient(replace(self.cfg, database=database))

    # Gestion des sessions: .session() ⇒ context manager lisible.
    @contextlib.contextmanager
    def session(self, *, readonly: bool = False, database: Optional[str] = None):
        s = self._driver.session(
            database=database or self.cfg.database,
            default_access_mode=READ_ACCESS if readonly else WRITE_ACCESS,
        )
        try:
            yield s
        except (ServiceUnavailable, AuthError, Neo4jError):
            log.exception("neo4j:session:error", extra={"db": database or self.cfg.database})
            raise
        finally:
            s.close()

    # Exécution de requêtes Cypher
    def run(self, query: str, params: Optional[Dict[str, Any]] = None,
            *, readonly: bool = False, database: Optional[str] = None):
        with self.session(readonly=readonly, database=database) as s:
            return list(s.run(query, params or {}))

    # Vérification de la connexion: timeout/retries au driver + ping()
    def ping(self) -> bool:
        try:
            self.run("RETURN 1 AS ok", readonly=True)
            return True
        except Exception:
            return False

# Petite fabrique pratique
def client_from_settings(settings) -> Neo4jClient:
    neo = settings.neo4j
    return Neo4jClient(Neo4jConfig(
        uri=str(neo.uri),
        username=str(neo.username),
        password=str(neo.password),
        database=str(neo.database),
        connection_timeout=float(getattr(neo, "timeout", 15.0)),
    ))
