from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from adapters.db.neo4j import Neo4jAdapter, client_from_settings
from .schemas import SearchRequest, SearchResponse, Hit

@dataclass
class KGRetriever:
    """
    Récupérateur de connaissances utilisant Neo4j.
    """
    db: Neo4jAdapter

    @staticmethod
    def _base_cypher(series_filter: bool, type_filter: bool) -> str:
        """Construit la requête de base pour la recherche."""
        # Full‑text sur Entity.name → hits entités
        where_series = "AND ($series IS NULL OR e.series = $series)" if series_filter else ""
        where_type   = "AND ($type IS NULL OR e.type = $type)" if type_filter else ""
        return f"""
        CALL db.index.fulltext.queryNodes('entity_name_ft', $q) YIELD node, score
        WITH node AS e, score
        WHERE 1=1 {where_series} {where_type}
        RETURN elementId(e) AS id, labels(e) AS labels, e.name AS name, e.type AS type,
               coalesce(e.series, '') AS series, score
        ORDER BY score DESC
        LIMIT $k
        """

    def search(self, req: SearchRequest) -> SearchResponse:
        """Exécute une recherche en utilisant l'index spécifié."""
        q = self._base_cypher(series_filter=True, type_filter=("type" in req.filters))
        params: Dict[str, Any] = {
            "q": req.query, "k": int(req.k),
            "series": req.series, "type": req.filters.get("type")
        }
        with self.db._session() as s:
            rows = [r.data() for r in s.run(q, **params)]
        hits: List[Hit] = []
        for r in rows:
            hits.append(Hit(
                id=r["id"], score=float(r["score"]),
                label=(r["labels"][0] if r["labels"] else "Entity"),
                name=r.get("name"), type=r.get("type")
            ))
        return SearchResponse(query=req.query, mode="kg", hits=hits, cypher=q, params=params)
