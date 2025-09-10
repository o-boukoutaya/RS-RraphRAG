from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict, Any
import yaml, os

@dataclass
class RuntimeCfg:
    model: str = "gpt-4o-mini"
    max_tokens: int = 700
    temperature: float = 0.1
    parallelism: int = 8

@dataclass
class BudgetsCfg:
    token_max: int = 3000
    token_guardrail_global: int = 1200
    token_guardrail_path: int = 900

@dataclass
class RouterCfg:
    confidence_min: float = 0.62
    intent_rules: Dict[str, List[str]] = field(default_factory=lambda: {"global_keywords": []})

@dataclass
class PathRagCfg:
    N: int = 40
    K: int = 15
    alpha: float = 0.8
    theta: float = 0.05
    lite: Dict[str, int] = field(default_factory=lambda: {"N": 20, "K": 5})

@dataclass
class GraphRagCfg:
    levels: List[str] = field(default_factory=lambda: ["C0","C1","C2","C3"])
    default_level: str = "C0"
    escalate_if_conf_low: bool = True

@dataclass
class ELCfg:
    topk_bm25: int = 20
    topk_dense: int = 20
    allow_none: bool = True

@dataclass
class OntologyCfg:
    schema: str = "./ontology.yaml"

@dataclass
class AppKgCfg:
    runtime: RuntimeCfg = field(default_factory=RuntimeCfg)
    budgets: BudgetsCfg = field(default_factory=BudgetsCfg)
    router: RouterCfg = field(default_factory=RouterCfg)
    pathrag: PathRagCfg = field(default_factory=PathRagCfg)
    graphrag: GraphRagCfg = field(default_factory=GraphRagCfg)
    el: ELCfg = field(default_factory=ELCfg)
    ontology: OntologyCfg = field(default_factory=OntologyCfg)
