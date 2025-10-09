from typing import List, Tuple, Dict, Any, Optional, Iterable
from app.core.resources import get_db, get_provider
from graph_based.utils.types import NodeRecord, EdgeRecord, Community, BuildReport, Summary

from graph_based.kg.build import canonicalize, graph_store
from graph_based.kg.el import augment
from graph_based.kg.community import hierarchy, leiden
from graph_based.kg.summarize import comm_summaries, index_search
import time

def run(series: str, options: Dict[str, Any]) -> BuildReport:
    """
    Orchestrateur 'build' (appelé par la route HTTP).
    Steps:
      1) nodes,edges = canonicalize.run(series, db=db, provider=provider, min_conf=options.get("min_conf",0.35))
      2) nodes,edges = el.augment.run(series, nodes, edges, db=db, provider=provider)
      3) write       = graph_store.upsert(series, nodes, edges, db=db)
      4) comms       = leiden.detect(series, edges, db=db, levels=options["community"]["levels"], resolution=options["community"]["resolution"])
      5) hierarchy.wire(series, comms, db=db)
      6) sums        = comm_summaries.make(series, comms, options["summaries"]["levels"], db=db, provider=provider)
      7) indexes     = index_search.sync(series, db=db)
      8) return BuildReport
    """
    # database et provider LLM depuis resources
    db, provider = get_db(), get_provider()
    
    # S'assurer de l'existence des contraintes
    graph_store.ensure_constraints(db=db)

    start_time = time.perf_counter()
    # 1. Canonicalisation + validation
    nodes, edges = canonicalize.run(series, min_conf=options.get("min_conf",0.35))

    # 2. Enrichissement / alignement
    nodes, edges = augment.run(series, nodes, edges)

    # 3. Persistance dans le KG (upsert transactionnel)
    write = graph_store.upsert(series, nodes, edges)

    # 4. Détection de communautés hiérarchiques (Leiden)
    comms = leiden.detect(series, levels=options["community"]["levels"], resolution=options["community"]["resolution"])

    # 5. Filtrage et hiérarchisation des communautés
    hierarchy.wire(series, comms, db=db)

    # 6. Résumés de communautés (C0/C1)
    sums = comm_summaries.make(series, comms, options["summaries"]["levels"], db=db, provider=provider)

    # 7. Index de recherche (dense + sparse)
    indexes = index_search.sync(series, db=db, provider=provider)
    
    # 8. Rapport de build
    return  {
      "series": series,
      "nodes": len(nodes), "edges": len(edges),
      "communities": {f"L{i}": len(c) for i,c in enumerate(comms)},
      "summaries": {f"C{i}": len(s) for i,s in enumerate(sums)},
      "indexes": {f"{k}_index": f"{k}_index_{series}" for k in ["chunks", "node"]},
      "elapsed_s": time.perf_counter() - start_time,
      "warnings": []  
    }