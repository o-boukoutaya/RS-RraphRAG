# corpus/kg/extract.py
from __future__ import annotations
import json, re, time, hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
from corpus.kg.prompts import build_extraction_prompt

def _strip_code_fences(s: str) -> str:
    """Supprime les fences de code (```...```) d'une chaîne."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()

def _coerce_json(s: str) -> Dict[str, Any]:
    """Rend un JSON dict même si le modèle renvoie des décorations légères."""
    s = _strip_code_fences(s)
    # capture le premier bloc {...} équilibré si présent
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        s = m.group(0)
    try:
        return json.loads(s)
    except Exception:
        # heuristique douce: supprimer trailing commas
        s = re.sub(r",\s*([}\]])", r"\1", s)
        return json.loads(s)

def _slug(s: str) -> str:
    """Crée un slug simple (a-z0-9-) à partir d'une chaîne."""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\- _]", "", s)
    return s.replace(" ", "-")[:128] or "x"

def canonical_entity_id(series: str, typ: str, name: str) -> str:
    """Crée un ID d'entité canonique à partir des métadonnées."""
    base = f"{series}|{typ}|{_slug(name)}"
    # stable + compact
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"{series}:{typ}:{_slug(name)}:{h}"

@dataclass
class KGExtraction:
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    ts: float

def extract_from_text(text: str, *, provider, series: str, file: str, page: Optional[int], chunk_id: str,
                      domain_hint: str = "immobilier") -> KGExtraction:
    """
    Appelle le provider chat (ask_llm) avec un prompt structuré, parse le JSON,
    normalise en ajoutant ids et méta minimales (series, source...).
    """
    prompt = build_extraction_prompt(text, domain_hint=domain_hint)
    raw = provider.ask_llm(prompt)
    data = _coerce_json(raw)

    ts = time.time()
    ents_in = data.get("entities") or []
    rels_in = data.get("relations") or []

    entities: List[Dict[str, Any]] = []
    for e in ents_in:
        typ = (e.get("type") or "").strip() or "Thing"
        name = (e.get("name") or "").strip()
        if not name:
            continue
        eid = canonical_entity_id(series, typ, name)
        entities.append({
            "id": eid,
            "name": name,
            "type": typ,
            "series": series,
            "props": e.get("props") or {},
            "ts": ts,
        })

    relations: List[Dict[str, Any]] = []
    for r in rels_in:
        typ = (r.get("type") or "").strip().upper() or "RELATED_TO"
        src = r.get("source") or {}
        dst = r.get("target") or {}
        s_typ, s_name = (src.get("type") or "Thing"), (src.get("name") or "").strip()
        d_typ, d_name = (dst.get("type") or "Thing"), (dst.get("name") or "").strip()
        if not s_name or not d_name:
            continue
        sid = canonical_entity_id(series, s_typ, s_name)
        did = canonical_entity_id(series, d_typ, d_name)
        relations.append({
            "src": sid,
            "dst": did,
            "type": typ,
            "props": r.get("props") or {},
            "confidence": float(r.get("confidence") or 0.0),
            "source": chunk_id,
            "ts": ts,
        })

    return KGExtraction(entities=entities, relations=relations, ts=ts)
