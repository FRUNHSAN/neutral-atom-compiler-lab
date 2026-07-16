"""
schema.py — 约束式工程三层数据模型。

Constraint:  "应该是什么" — formal, rigidity, stage
Boundary:    "错了扣多少分" — cost_terms, cost_groups, assumptions
Bridge:      "两个约束之间的张力怎么解决" — type, resolve_fn, coupled
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Rigidity(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    OBJECTIVE = "objective"


class Stage(str, Enum):
    DISCOVERY = "discovery"
    TRANSLATION = "translation"
    REDUCED = "reduced"
    IMPLEMENTED = "implemented"

    def can_jump_to(self, target: Stage) -> bool:
        order = list(Stage)
        return abs(order.index(self) - order.index(target)) <= 1


class BridgeType(str, Enum):
    IMPLEMENTS = "implements"
    REFINES = "refines"
    SUBSTITUTES = "substitutes"
    CONFLICTS = "conflicts_with"
    TENSION = "tension"
    EQUIVALENCE = "equivalence"
    DERIVES = "derives_from"


class ResolveFn(str, Enum):
    COMPARE = "compare"
    WEIGHTED = "weighted"
    SOLVER = "solver"


@dataclass
class Constraint:
    id: str
    name: str
    stage: Stage
    formal: str
    rigidity: Rigidity
    domain_tags: list[str] = field(default_factory=list)
    G_C: float = 0.0
    derives_from: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class CostTerm:
    formula: str
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class Boundary:
    id: str
    constraint: str
    implements_formal: str
    stage: Stage
    domain_tags: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    cost_terms: dict[str, CostTerm] = field(default_factory=dict)
    cost_groups: dict[str, list[str]] = field(default_factory=dict)
    discretization_gap: str = ""


@dataclass
class Bridge:
    id: str
    type: BridgeType
    source: str
    target: str
    mediation: str
    resolve_fn: ResolveFn
    coupled: bool = False
    solver_timeout_ms: int = 50
    solver_fallback: str = ""
    domain_tags: list[str] = field(default_factory=list)
