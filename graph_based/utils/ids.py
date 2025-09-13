import hashlib

def stable_id(*parts: str) -> str:
    s = "::".join(p.strip().lower() for p in parts if p)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def node_id(series: str, name: str, type_: str) -> str:
    """Construit un ID stable (hash) pour les nœuds."""
    return stable_id(series, name, type_)
