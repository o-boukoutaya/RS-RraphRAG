

# graph_based/prompts/__init__.py

from pathlib import Path
# from . import qfs_map, qfs_reduce, path_prompt

def render_template(path: str, **vars) -> str:
    """
    Rend un prompt .md qui utilise {{series}}, {{cid}}, {{chunk_text}}
    en échappant toutes les accolades JSON, puis en ré-injectant
    uniquement les placeholders variables avant str.format.
    """
    raw = Path(path).read_text(encoding="utf-8")

    # 1) Échapper toutes les accolades littérales (JSON, exemples, etc.)
    esc = raw.replace("{", "{{").replace("}", "}}")

    # 2) Ré-injecter les placeholders variables ({{series}} -> {series}, etc.)
    for k in vars.keys():
        esc = esc.replace("{{{{" + k + "}}}}", "{" + k + "}")

    # 3) Appliquer str.format pour substituer les valeurs
    try:
        return esc.format(**vars)
    except Exception as e:
        raise RuntimeError(f"Erreur de format dans le prompt '{path}': {e}")
