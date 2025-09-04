from __future__ import annotations
from typing import Dict
from dataclasses import dataclass
from .schemas import SearchRequest, SearchResponse, Hit
from .kg import KGRetriever
from .dense import DenseRetriever

@dataclass
class HybridRetriever:
    kg: KGRetriever
    dense: DenseRetriever

    def search(self, req: SearchRequest) -> SearchResponse:
        """Effectue une recherche hybride combinant KG et dense."""
        kg_res = self.kg.search(req)
        dn_res = self.dense.search(req)

        # Fusion simple par id avec pondération
        alpha, beta = 0.6, 0.4
        bucket: Dict[str, Hit] = {}

        # Fonction d'ajout au bucket
        def push(h: Hit, w: float):
            """Ajoute un hit au bucket avec un poids donné."""
            if h.id in bucket:
                bucket[h.id].score += w * h.score
                # enrichir le texte si absent
                if not bucket[h.id].text and h.text:
                    bucket[h.id].text = h.text
            else:
                bh = h.model_copy(deep=True)
                bh.score = w * bh.score
                bucket[h.id] = bh

        for h in kg_res.hits: push(h, alpha)
        for h in dn_res.hits: push(h, beta)

        # Trier et limiter les résultats
        hits = sorted(bucket.values(), key=lambda x: x.score, reverse=True)[:req.k]

        # Retourner la réponse hybride
        return SearchResponse(
            query=req.query, mode="hybrid", hits=hits,
            diagnostics={"kg_hits": len(kg_res.hits), "dense_hits": len(dn_res.hits)}
        )
