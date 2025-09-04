from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.core.resources import get_provider
from adapters.db.neo4j import Neo4jAdapter
from .schemas import SearchRequest, SearchResponse, Hit

@dataclass
class DenseRetriever:
    """Récupérateur dense utilisant des embeddings et Neo4j."""
    db: Neo4jAdapter

    def _embed(self, text: str) -> Optional[List[float]]:
        """Crée une représentation vectorielle à partir d'un texte."""
        prov = get_provider()
        # L’embedder peut être absent → fallback None
        if prov and hasattr(prov, "embed"):
            try:
                return list(prov.embed(text))
            except Exception:
                return None
        return None

    def _vector_query(self, index_name: str, vec: List[float], k: int) -> List[Dict[str, Any]]:
        """Exécute une requête vectorielle sur l'index spécifié."""
        q = """
        CALL db.index.vector.queryNodes($index, $k, $vec)
        YIELD node, score
        RETURN elementId(node) AS id, labels(node) AS labels, node.text AS text,
               node.page AS page, node.series AS series, node.doc_id AS doc_id,
               node.meta_json AS meta_json, score
        ORDER BY score DESC
        """
        with self.db._session() as s:
            return [r.data() for r in s.run(q, index=index_name, k=int(k), vec=list(vec))]

    def _fulltext_fallback(self, qstr: str, k: int, series: Optional[str]) -> List[Dict[str, Any]]:
        """Exécute une requête de recherche en texte intégral."""
        # nécessite: CREATE FULLTEXT INDEX chunk_text_ft IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]
        q = """
        CALL db.index.fulltext.queryNodes('chunk_text_ft', $q) YIELD node, score
        WITH node AS c, score
        WHERE $series IS NULL OR c.series = $series
        RETURN elementId(c) AS id, labels(c) AS labels, c.text AS text, c.page AS page,
               c.series AS series, c.doc_id AS doc_id, c.meta_json AS meta_json, score
        ORDER BY score DESC
        LIMIT $k
        """
        with self.db._session() as s:
            return [r.data() for r in s.run(q, q=qstr, k=int(k), series=series)]

    def search(self, req: SearchRequest) -> SearchResponse:
        """
        Exécute une recherche en utilisant l'index spécifié.
        """
        idx = req.index_name or "chunk_embedding_idx"
        vec = self._embed(req.query)
        diag: Dict[str, Any] = {"index": idx, "used": "vector" if vec else "fulltext"}
        rows = self._vector_query(idx, vec, req.k) if vec else self._fulltext_fallback(req.query, req.k, req.series)

        hits: List[Hit] = []
        for r in rows:
            hits.append(Hit(
                id=r["id"], score=float(r["score"]), text=r.get("text"),
                page=r.get("page"), filename=r.get("doc_id")   # si vous stockez le filename à part, adaptez
            ))
        return SearchResponse(query=req.query, mode="dense", hits=hits, diagnostics=diag)
