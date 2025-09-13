# kg/summarize/comm_summaries.py
from typing import List
from graph_based.utils.types import Community, Summary
from typing import List
from graph_based.utils import tokenize


def _render_comm_prompt(members_text: str, level: int) -> str:
    from pathlib import Path
    tpl = Path("graph_based/prompts/comm_summarize.md").read_text(encoding="utf-8")
    return tpl.format(level=level, members=members_text)

def _members_blob(db, series: str, level: int, cid: str, max_members: int = 40) -> str:
    # Top membres par degré (priorise les entités “centrales”)
    rows = db.run_cypher("""
    MATCH (c:Community {series:$series, level:$level, cid:$cid})<-[:IN_COMMUNITY {series:$series, level:$level}]-(e:Entity {series:$series})
    WITH e, size((e)-[:REL {series:$series}]-()) AS deg
    ORDER BY deg DESC LIMIT $k
    RETURN e.name AS name, e.type AS type, coalesce(e.desc, "") AS desc
    """, {"series": series, "level": level, "cid": cid, "k": max_members})

    lines = [f"- {r['name']} [{r['type']}]: {r['desc']}" for r in rows]
    # Tronquer pour respecter un budget de tokens
    blob = "\n".join(lines)
    return tokenize.fit(blob, max_tokens=1000)  # budget pour le contexte

# CYPHER pour 
CYPHER = """
MATCH (c:Community {series:$series, level:$level, cid:$cid})
SET c.summary = $summary
"""

def make(series: str, communities: List[Community], levels: List[str] = ["C0","C1"], *, db, provider, max_members: int = 40, max_tokens: int = 1200) -> List[Summary]:
    """
    Génère des résumés de communautés (C0..C3; SS/TS si activés).
    - Input: communities (avec level), niveaux à produire, budgets tokens.
    - Output: [{"community_id","level","kind","text","tokens"}...]
    - Note: pré-calcul offline; utilisé par QFS map/reduce.
    """
    done: List[Summary] = []
    target = set(levels)

    for c in communities:
        lvl = int(c["level"])
        if lvl not in target:
            continue
        cid = c["cid"] if "cid" in c else None
        if not cid:
            continue
    
        members_text = _members_blob(db, series, lvl, cid, max_members=max_tokens)
        prompt = _render_comm_prompt(members_text, lvl)
        prompt = tokenize.fit(prompt, max_tokens=max_tokens)  # garde‑fou

        summary = provider.ask_llm(prompt).strip()
        # persist summary dans le nœud Community
        db.run_cypher(CYPHER, {"series": series, "level": lvl, "cid": cid, "summary": summary})

        # done.append(f"{lvl}:{cid}")
        done.append({"community_id": cid, "level": lvl, "kind": "summary", "text": summary, "tokens": tokenize.count_tokens(summary)})

    return done