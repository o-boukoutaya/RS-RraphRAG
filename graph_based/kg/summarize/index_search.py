# graph_based/kg/summarize/index_search.py
import math
from typing import Any, Dict, List, Optional, Iterable
from graph_based.utils.tokenize import fit


# Index vectoriel (existe côté adapter) → db.create_vector_index(index, label, prop, dimensions, similarity='cosine')
# Écriture embeddings entités (upsert propriété evec sur :Entity) :
WRITE_ENTITY_VECS = """
UNWIND $rows AS r
MATCH (e:Entity {id:r.id})
SET e.evec = r.vec
"""

# Récupère les entités à indexer (desc fallback name)
GET_ENTITIES = """
MATCH (e:Entity) WHERE e.series = $series
RETURN e.id AS id, coalesce(e.desc, e.name) AS text
ORDER BY id
"""

# Écriture embeddings entités (upsert propriété evec sur :Entity) :
WRITE_ENTITY_VECS = """
UNWIND $rows AS r
MATCH (e:Entity {id:r.id})
SET e.evec = r.vec
"""

from app.observability.pipeline import pipeline_step
@pipeline_step("Graph Build - Summarization Index Sync")
def sync(series: str, *, db, provider, batch: int = 256, dim: int | None = None) -> Dict[str, Any]:
    """
    (Ré)indexe les artefacts de résumé et les communautés pour la recherche rapide.
    -> Construit 'nodeIndex_{series}' en encodant Entity.desc (fallback: name)
    - Output: {"node_index": "...", "community_index": "...", "chunk_index": "..."}
    """
    node_index = f"nodeIndex_{series}"
    chunks_index = f"chunkIndex_{series}"  # celui créé par corpus/Embedder

    # 1) Récupère les entités à indexer (desc fallback name)
    ents = db.run_cypher(GET_ENTITIES, {"series": series})
    items = [dict(r) for r in ents if r["text"]]

    # 2) Dimension
    if dim is None:
        caps = getattr(provider, "capabilities", lambda: {})() or {}
        dim = caps.get("dims", 768)  # fallback 768

    # 3) Création index si besoin
    if not db.check_index_exists(node_index):
        db.create_vector_index(node_index, label="Entity", prop="evec", dimensions=dim, similarity="cosine")

    # 4) Encodage batch + upsert evec
    buf = []
    for i in range(0, len(items), batch):
        chunk = items[i:i+batch]
        vecs = provider.embed_texts([x["text"] for x in chunk], dimensions=dim)
        for x, v in zip(chunk, vecs):
            buf.append({"id": x["id"], "vec": v})
        if len(buf) >= 1000:
            db.run_cypher(WRITE_ENTITY_VECS, {"rows": buf})
            buf.clear()
    if buf:
        db.run_cypher(WRITE_ENTITY_VECS, {"rows": buf})

    return {
        "nodes": len(items),
        "node_index": node_index,
        "chunks_index": chunks_index,
    }


# ------------------------ Search ----------------------

def _cosine(a: Iterable[float] | None, b: Iterable[float] | None) -> float:
    """Cosine similarity entre deux vecteurs."""
    if not a or not b:
        return 0.0
    ax = list(a); bx = list(b)
    if len(ax) != len(bx):  # tolérance
        m = min(len(ax), len(bx))
        ax, bx = ax[:m], bx[:m]
    dot = sum(x*y for x, y in zip(ax, bx))
    na = math.sqrt(sum(x*x for x in ax)) or 1.0
    nb = math.sqrt(sum(y*y for y in bx)) or 1.0
    return float(dot / (na * nb))

def _kw_overlap(text: str, query: str) -> float:
    """Score simple de recouvrement lexicale (tokens > 2 chars)."""
    qt = {t for t in query.lower().split() if len(t) > 2}
    tt = {t for t in text.lower().split() if len(t) > 2}
    if not qt or not tt: 
        return 0.0
    inter = len(qt & tt)
    return inter / float(len(qt))


def search(series: str, query: str, *, db, provider, levels: Optional[list[int]] = None, limit: int = 12, max_tokens_per_summary: int = 256) -> Dict[str, Any]: #List[Community]:
    """
    Trouve les communautés pertinentes pour une question 'global sensemaking'.
    - Output: top communautés (avec id, level, node_ids)
    
    Retourne les meilleurs 'candidats' (résumés de communautés) pour QFS.
    INPUTS
      - series: str
      - query: str
      - db: adapter Neo4j existant (dispose de run_cypher)
      - provider: adapter LLM/embeddings existant (dispose de embed)
      - levels: liste des niveaux (ex: [0] pour C0, [0,1] pour C0→C1). None => tous
      - limit: nb max de résumés renvoyés
      - max_tokens_per_summary: garde‑fou de longueur pour chaque résumé
    OUTPUT
      {
        "query_vec": [float] | None,
        "candidates": [
          {"id": str, "level": int, "text": str, "score": float}
        ]
      }
    Hypothèses de schéma:
      - (:Summary {id, series, level, text, vec?})
    """
    # 1) Embedding de la requête (si provider supporte)
    try:
        qvec = provider.embed(query)
    except Exception:
        qvec = None

    # 2) Récupération des résumés (C0..Ck)
    cypher = """
    MATCH (s:Summary {series:$series})
    WHERE $levels IS NULL OR s.level IN $levels
    RETURN s.id AS id, s.level AS level, s.text AS text, s.vec AS vec
    """
    rows = [r for r in db.run_cypher(cypher, {"series": series, "levels": levels})]

    # 3) Scorage (cosine si vec dispo sinon simple recouvrement lex.)
    cands: List[Dict[str, Any]] = []
    for r in rows:
        text = r.get("text") or ""
        text = fit(text, max_tokens=max_tokens_per_summary)
        vec = r.get("vec")
        score = _cosine(qvec, vec) if (qvec and vec) else _kw_overlap(text, query)
        cands.append({
            "id": r["id"],
            "level": int(r.get("level", 0)),
            "text": text,
            "score": float(score),
        })

    cands.sort(key=lambda x: x["score"], reverse=True)
    # {"id","level","node_ids":[...],"parent_id":str|None}
    return {
        "query_vec": qvec,
        "candidates": cands[:limit],
    }