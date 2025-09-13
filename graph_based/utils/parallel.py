from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Callable, List, Any

def _pmap(fn: Callable[[Any], Any], items: Iterable[Any], max_workers: int = 8) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(fn, x) for x in items]
        return [f.result() for f in as_completed(futs)]

def map_unordered(fn, items: List[Any], *, max_workers: int = 8) -> List[Any]:
    """Exécute `fn` en parallèle ; renvoie les résultats dès qu’ils arrivent (QFS map)."""
    return _pmap(fn, items, max_workers=max_workers)