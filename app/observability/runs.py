from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

RUNS_DIR = Path("data/runs"); RUNS_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class StepState:
    name: str; status: str = "pending"; ms: float|None = None; error: str|None = None

@dataclass
class RunState:
    """ Représente l'état d'un run de pipeline de construction de graph."""
    run_id: str; series: str; pipeline: str = "graph_build"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str|None = None; status: str = "running"
    steps: dict[str, StepState] = field(default_factory=dict)

def create_run(series: str, steps: list[str]) -> RunState:
    """ Initialise un nouvel état de run avec les étapes spécifiées."""
    rid = f"gb:{series}:{uuid.uuid4().hex[:8]}"
    st = RunState(run_id=rid, series=series, steps={s: StepState(name=s) for s in steps})
    _save_run(st); return st

def mark_step(r: RunState, step: str, status: str, ms: float|None=None, error: str|None=None):
    """ Met à jour l'état d'une étape spécifique dans le run."""
    s = r.steps[step]; s.status = status; s.ms = ms; s.error = error; _save_run(r)

def finish_run(r: RunState, status: str):
    """ Marque le run comme terminé avec le statut spécifié."""
    r.status = status; r.finished_at = datetime.now(timezone.utc).isoformat(); _save_run(r)

def _save_run(r: RunState):
    """ Enregistre l'état du run dans un fichier JSON."""
    with open(RUNS_DIR / f"{r.run_id}.json", "w", encoding="utf-8") as f:
        json.dump(asdict(r), f, ensure_ascii=False, indent=2)
