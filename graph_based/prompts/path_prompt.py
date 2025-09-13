SYSTEM = "You answer ONLY using the provided graph PATHS. If insufficient, say 'Not enough evidence'."
def render(q, paths):
    from graph_based.retriever.pathrag.prompt_builder import _Serializer
    import json
    return json.dumps({"question": q, "paths": _Serializer.serialize_paths(paths)}, ensure_ascii=False)
