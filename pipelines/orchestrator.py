# pipelines/orchestrator.py
from dataclasses import dataclass
from typing import Callable, Dict, List

@dataclass
class Step:
    name: str
    run: Callable[[Dict], Dict]   # in/out dict (state)

class Orchestrator:
    def __init__(self, steps: List[Step]): self.steps = steps
    def execute(self, state: Dict) -> Dict:
        for s in self.steps:
            state = s.run(state)
        return state

# /pipelines/run → exécute import -> extract -> chunk -> embed -> kg
# /corpus/... → expose chaque étape séparément (manuel)