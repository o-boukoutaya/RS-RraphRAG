from __future__ import annotations
import json
import re
from typing import List, Tuple, Dict, Any
from graph_based.utils.types import NodeRecord, EdgeRecord
from collections import defaultdict
from utils.ids import node_id, stable_id

# ---------------- Prompt LLM ----------------

def render_el_prompt(mention: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    # charge le prompt contenu depuis prompts/el_entgpt.md
    from pathlib import Path
    prompt_md = Path("prompts/el_entgpt.md").read_text(encoding="utf-8")
    prompt = prompt_md.format(mention=mention, candidates=candidates)
    return prompt

def _safe_parse_json(s: str) -> dict:
    # 1) tentative directe
    try:
        return json.loads(s)
    except Exception:
        pass
    # 2) fallback: extraire le 1er bloc {...}
    m = re.search(r'\{.*\}', s, flags=re.S)
    if not m:
        return {"winner": "NONE"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"winner": "NONE"}

# ---------------- run ----------------

def run(series: str, nodes: List[NodeRecord], edges: List[EdgeRecord], *, db, provider) -> Tuple[List[NodeRecord], List[EdgeRecord]]:
    """
    Enrichit/alimente le KG par désambiguïsation et alignement (EntGPT-like).
    - Input: nodes/edges issus de canonicalize.run
    - Process:
        a) candidates.generate(...) → top candidats par mention.
        b) select.choose(...) → sélection 'multi-choice' (avec option 'None').
        c) fusion: merge attributs/aliases/sources ; suppression des doublons.
        d) complétion légère de relations manquantes (synonym/isA/contains si robustes).
    - Output: nodes', edges' (qualifiés, moins de doublons).
    - Side-effects: aucun (upsert délégué à graph_store).
    """
    # 1) CANDIDATES — blocking par fingerprint
    by_fp = defaultdict(list)
    def fp(name: str) -> str:
        s = ''.join(ch for ch in name.lower() if ch.isalnum() or ch.isspace())
        s = ' '.join(w for w in s.split() if len(w) > 2)  # vire stop-words courts
        return s[:64]

    for n in nodes:
        n["_fp"] = fp(n["name"])
        by_fp[n["_fp"]].append(n)

    # 2) SELECTION — par groupe de fingerprint
    id_map = {}  # old_node_id -> canonical_node_id
    new_nodes = []
    for fp_key, group in by_fp.items():
        if len(group) == 1:
            g = group[0]
            id_map[g["id"]] = g["id"]
            new_nodes.append(g)
            continue

        # Préparer un "ancrage" (la 1ère entrée comme mention) + autres comme candidats.
        mention = group[0]
        candidates = [
            { "id": g["id"], "name": g["name"], "type": g.get("type",""),
              "desc": (g.get("desc") or "")[:160] } for g in group
        ]
        prompt = render_el_prompt(mention=mention, candidates=candidates)
        raw = provider.ask_llm(prompt)
        data = _safe_parse_json(raw)
        winner = data.get("winner") or "NONE"
        if winner == "NONE":
            # on garde chaque entrée, pas de fusion
            for g in group:
                id_map[g["id"]] = g["id"]
                new_nodes.append(g)
        else:
            # Fusionner vers winner
            canon = next((g for g in group if g["id"] == winner), group[0])
            aliases = set(canon.get("aliases", [])) | {g["name"] for g in group if g["id"] != winner}
            cids = set(canon.get("cids", []))
            for g in group:
                cids |= set(g.get("cids", []))
                id_map[g["id"]] = winner
            canon["aliases"] = sorted(aliases)[:20]
            canon["cids"] = sorted(cids)
            new_nodes.append(canon)

    # 3) Re-map des RELATIONS et consolidation du prédicat
    new_edges = []
    seen = set()
    for e in edges:
        src = id_map.get(e["src_id"], e["src_id"])
        dst = id_map.get(e["dst_id"], e["dst_id"])
        eid = stable_id(series, src, e["pred"], dst)
        key = (src, e["pred"], dst)
        if key in seen:
            # fusion cids/conf
            for ee in new_edges:
                if ee["id"] == eid:
                    ee["cids"] = sorted(set(ee["cids"]) | set(e["cids"]))
                    ee["conf"] = max(ee.get("conf",0.0), e.get("conf",0.0))
                    break
        else:
            new_edges.append({
                "id": eid, "src_id": src, "dst_id": dst,
                "pred": e["pred"], "cids": list(e["cids"]), "conf": float(e.get("conf",0.0))
            })
            seen.add(key)

    return new_nodes, new_edges