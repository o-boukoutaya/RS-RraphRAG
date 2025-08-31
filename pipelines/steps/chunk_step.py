# pipelines/steps/chunk_step.py
from __future__ import annotations
from typing import Any, Dict, Optional
from corpus.chunker import ChunkRunner, ChunkOptions

class ChunkStep:
    """Étape pipeline : chunking d'une série après extraction."""
    def __init__(self, default_opts: Optional[ChunkOptions] = None) -> None:
        self.default_opts = default_opts or ChunkOptions()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        series = state.get("series")
        if not series:
            raise ValueError("ChunkStep: 'series' requis dans le state")
        opts = ChunkOptions(
            strategy=state.get("chunk_strategy", self.default_opts.strategy),
            size=int(state.get("chunk_size", self.default_opts.size)),
            overlap=int(state.get("chunk_overlap", self.default_opts.overlap)),
            separators=tuple(state.get("chunk_separators", self.default_opts.separators)),
            use_llm=bool(state.get("chunk_use_llm", self.default_opts.use_llm)),
        )
        runner = ChunkRunner(opts)
        report = runner.run_series(series)
        state["chunk_report"] = report
        return state
