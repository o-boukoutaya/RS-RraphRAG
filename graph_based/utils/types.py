# utils/types.py (optionnel si vous voulez factoriser)

from typing import List, Tuple, Dict, Any, Optional, Iterable

BuildReport = Dict[str, Any]  # {"series","nodes","edges","communities":{"L0":..},"summaries":{"C0":..},"indexes":{"node_index":..},"elapsed_s","warnings":[..]} 

NodeRecord = Dict[str, Any]   # {"id","name","type","attrs","sources":[cid,...]}
EdgeRecord = Dict[str, Any]   # {"id","src","dst","type","desc","sources":[cid,...]}
ChunkRef   = Dict[str, Any]   # {"cid","series","file","page","order","text?","vec?": [float,...]}

Community = Dict[str, Any]    # {"id","level","node_ids":[...],"parent_id":str|None}
Summary   = Dict[str, Any]    # {"community_id","level","kind":"C0|C1|C2|C3|TS|SS","text", "tokens"}

PathRef   = Dict[str, Any]    # {"nodes":[node_id,...], "edges":[edge_id,...], "score": float, "sources":[cid,...]}

QFSMapOut = Dict[str, Any]    # {"community_id","partial_answer","score","citations":[...]}
QFSFinal  = Dict[str, Any]    # {"answer","citations":[...], "used_levels":["C0","C1"], "communities":[...]}
