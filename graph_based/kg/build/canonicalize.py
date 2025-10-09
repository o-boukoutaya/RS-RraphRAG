
from cmath import log
import json, re
from typing import Any, Tuple, List

from app.core.resources import get_db, get_provider
from graph_based.utils.types import NodeRecord, EdgeRecord
from graph_based.utils.tokenize import fit
from graph_based.utils.ids import node_id, stable_id
from graph_based.prompts import render_template

from app.core.logging import get_logger
logger = get_logger(__name__)

# --- DEBUG HOOKS (à laisser en prod, neutres) ---
from pathlib import Path
import json, time
DEBUG_DIR = Path(f"data/debug/canonicalize")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

def _safe_parse_json(s: str) -> dict:
    # 1) tentative directe
    try:
        return json.loads(s)
    except Exception:
        pass
    # 2) fallback: extraire le 1er bloc {...}
    m = re.search(r'\{.*\}', s, flags=re.S)
    if not m:
        return {"entities": [], "relations": []}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"entities": [], "relations": []}

def render_canonicalize_prompt(series: str, cid: str | None, chunk_text: str) -> str:
    return render_template(
        "graph_based/prompts/kg_canonicalize.md",
        series=series,
        cid=cid or "",
        chunk_text=chunk_text,
    )



def run(series: str, *, min_conf: float = 0.35, max_ctx_tokens: int = 1200) -> Tuple[List[NodeRecord], List[EdgeRecord]]:
    """
    Canonicalise et (re)construit la couche 'information' du KG à partir des chunks indexés pour `series`.
    - Input:
        series: identifiant de la collection (ex: "cat-2025-Q1").
        db:    instance Neo4jAdapter (déjà injectée par notre app).
        provider: Provider LLM (utilisé pour petites normalisations sémantiques optionnelles).
        min_conf: score mini pour accepter une relation extraite.
    - Process (atomique côté appelant):
        1) Parcourt les chunks de la série (via métadonnées: index chunks existant).
        2) Extrait/normalise les mentions -> noeuds (merge par clés canoniques; noms normalisés).
        3) Agrège/filtre les relations (E-R-E) avec `min_conf`.
        4) On n'écrit pas en base: retourne des listes prêtes à upsert.
    - Output:
        nodes: [{id,name,type,attrs,sources:[cid,...]}]
        edges: [{id,src,dst,type,desc,sources:[cid,...]}]
    - Erreurs:
        - ValueError si `series` introuvable.
    - Appelé par: pipelines.build_graph.run
    """
    # database et provider LLM depuis resources
    db, provider = get_db(), get_provider()

    min_conf = float(min_conf or 0.0)
    nodes, edges = [], []
    seen_node_key = set()   # (name_lower, type)
    seen_edge_key = set()   # (src_id, pred, dst_id)

    db_chunks = db.stream_chunks(series)
    if not db_chunks:
        raise ValueError(f"series '{series}' not found or has no chunks")
    
    for i, rec in enumerate(db_chunks):
        cid = rec["id"] if "id" in rec else rec.get("cid")  # harmoniser si besoin
        text = rec["text"] or ""
        if i < 2: print("chunk", i, cid, text[:80])

        # garde-fou contexte pour ask_llm
        text_fit = fit(text, max_tokens=max_ctx_tokens)

        prompt = render_canonicalize_prompt(  # charge prompts/kg_canonicalize.md puis format
            series=series, cid=cid, chunk_text=text_fit
        )
        raw = provider.ask_llm(prompt)
        if i < 2:
            print(f"[canonicalize] cid={cid} raw_out[:240]={raw[:240]}")
        data = _safe_parse_json(raw)

        # -- ENTITIES --
        for e in data.get("entities", []):
            conf = float(e.get("conf", 0.0)) # confiance de l’extraction
            if conf < min_conf or not e.get("name") or not e.get("type"):
                continue
            key = (e["name"].strip().lower(), e["type"].strip().lower())
            nid = node_id(series, e["name"], e["type"])
            if key not in seen_node_key:
                nodes.append({
                    "id": nid, "series": series,
                    "name": e["name"], "type": e["type"],
                    "aliases": e.get("aliases", []),
                    "desc": e.get("desc", ""),
                    "cids": [cid], "conf": conf
                })
                seen_node_key.add(key)
            else:
                # cumuler la trace d'évidence
                for n in nodes:
                    if node_id(series, n["name"], n["type"]) == nid:
                        if cid not in n["cids"]: # éviter doublon
                            n["cids"].append(cid) # trace la source
                        n["conf"] = max(n.get("conf", 0.0), conf) # max confiance
                        break

        # -- RELATIONS --
        for r in data.get("relations", []):
            conf = float(r.get("conf", 0.0)) # confiance de l’extraction
            if conf < min_conf or not r.get("src") or not r.get("dst") or not r.get("pred"):
                continue
            src_id = node_id(series, r["src"],   # même nom/type qu’entités (type inconnu ici → "concept")
                             "concept")
            dst_id = node_id(series, r["dst"], "concept")
            eid = stable_id(series, src_id, r["pred"], dst_id)
            k = (src_id, r["pred"], dst_id)
            if k not in seen_edge_key:
                edges.append({
                    "id": eid, "src_id": src_id, "dst_id": dst_id,
                    "pred": r["pred"], "cids": [cid], "conf": conf
                })
                seen_edge_key.add(k)
            else:
                for e2 in edges:
                    if e2["id"] == eid:
                        if cid not in e2["cids"]:
                            e2["cids"].append(cid)
                        e2["conf"] = max(e2.get("conf", 0.0), conf)
                        break
    return nodes, edges