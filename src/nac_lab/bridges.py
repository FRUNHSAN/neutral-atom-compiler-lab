"""
bridges.py — Bridge declaration and swap infrastructure.

A Bridge represents a single decision point in a compiler that can be
replaced without modifying the compiler's source code.  Each bridge:

  - declares WHAT tension it resolves (source_constraint → target_constraint)
  - specifies HOW to resolve it (resolve_fn)
  - provides a PLUGGABLE adapter for alternative strategies
  - defines a BENCHMARK protocol for comparing strategies

This module provides the base classes and the registry for the 6 bridges
identified in ZAP (IEEE TQE 2026).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class BridgeType(str, Enum):
    """The 7 bridge types in the constraint-engineering taxonomy."""
    IMPLEMENTS = "implements"
    REFINES = "refines"
    SUBSTITUTES = "substitutes"
    CONFLICTS = "conflicts_with"
    TENSION = "tension"
    EQUIVALENCE = "equivalence"
    DERIVES = "derives_from"


class ResolveFn(str, Enum):
    """How a bridge's tension is resolved."""
    COMPARE = "compare"       # Compare two alternatives numerically
    WEIGHTED = "weighted"     # Weighted sum of competing objectives
    SOLVER = "solver"         # External solver required (coupled bridges)


@dataclass
class Bridge:
    """Declaration of one compiler decision point."""
    id: str
    name: str
    type: BridgeType
    source_constraint: str
    target_constraint: str
    resolve_fn: ResolveFn
    description: str
    coupled: bool = False
    default_strategy: str = ""
    alternative_strategy: str = ""
    zap_location: str = ""  # Where in ZAP source this decision lives


# ── The 6 ZAP bridges ────────────────────────────────────

BRIDGES: dict[str, Bridge] = {
    "BR-keep-vs-move": Bridge(
        id="BR-keep-vs-move",
        name="Keep vs Move Decision",
        type=BridgeType.TENSION,
        source_constraint="C-qc-crosstalk",
        target_constraint="C-qc-transport",
        resolve_fn=ResolveFn.SOLVER,
        description=(
            "For each idle qubit in the entanglement zone during a Rydberg stage: "
            "STAY and suffer crosstalk loss, or MOVE back to storage and pay transfer cost. "
            "This is the ONLY high-sensitivity bridge among ZAP's 6 decision points."
        ),
        coupled=True,
        default_strategy="hard_threshold (ZAP Eq.15)",
        alternative_strategy="AL soft decision (joint slot-constrained optimization)",
        zap_location="placer.py: idle qubit handling (~15 lines)",
    ),
    "BR-parallel-vs-distance": Bridge(
        id="BR-parallel-vs-distance",
        name="Parallelism vs Transport Distance",
        type=BridgeType.TENSION,
        source_constraint="C-qc-bandwidth",
        target_constraint="C-qc-transport",
        resolve_fn=ResolveFn.WEIGHTED,
        description=(
            "λ_par controls the trade-off between parallel gate execution and "
            "atom transport distance.  ZAP defaults to λ=1000, heavily favoring "
            "parallelism.  Our experiments show this parameter is NOT sensitive "
            "at TQE benchmark scales (10-30 qubits)."
        ),
        default_strategy="λ_par = 1000 (fixed)",
        alternative_strategy="Circuit-adaptive λ_par(n_q, n_2q, density)",
        zap_location="router.py: λ_par in routing cost function",
    ),
    "BR-parking-displacement": Bridge(
        id="BR-parking-displacement",
        name="Parking Displacement Strategy",
        type=BridgeType.SUBSTITUTES,
        source_constraint="C-qc-parking",
        target_constraint="C-qc-parking",
        resolve_fn=ResolveFn.COMPARE,
        description=(
            "After completing a gate, where does the atom return in the storage zone? "
            "ZAP parks at exactly 1 site displacement.  We tested up to 5 sites — "
            "slightly worse fidelity (more movement)."
        ),
        default_strategy="1 site displacement",
        alternative_strategy="Adaptive (up to 5 sites)",
        zap_location="placer.py: parking site selection",
    ),
    "BR-asap-strategy": Bridge(
        id="BR-asap-strategy",
        name="ASAP Scheduling Strategy",
        type=BridgeType.SUBSTITUTES,
        source_constraint="C-qc-depth",
        target_constraint="C-qc-depth",
        resolve_fn=ResolveFn.COMPARE,
        description=(
            "ZAP uses 'asap_separate' scheduling (gates scheduled as early as possible, "
            "independent per qubit).  'asap_joint' considers joint constraints. "
            "Delta = 0 on all tested circuits."
        ),
        default_strategy="asap_separate",
        alternative_strategy="asap_joint",
        zap_location="scheduler.py: scheduling strategy selection",
    ),
    "BR-qubit-priority": Bridge(
        id="BR-qubit-priority",
        name="Qubit Priority Weight",
        type=BridgeType.SUBSTITUTES,
        source_constraint="C-qc-slot-assignment",
        target_constraint="C-qc-slot-assignment",
        resolve_fn=ResolveFn.COMPARE,
        description=(
            "Which qubits get priority for entanglement zone slots? "
            "ZAP uses w=1/(l+1) where l is the layer index. "
            "Reuse-aware weighting shows Δ=0 at TQE benchmark scales."
        ),
        default_strategy="w = 1/(l+1) (layer-based)",
        alternative_strategy="Reuse-aware priority",
        zap_location="placer.py: init_mapping weight assignment",
    ),
    "BR-idle-cost-alpha": Bridge(
        id="BR-idle-cost-alpha",
        name="Idle Cost Alpha Coefficient",
        type=BridgeType.TENSION,
        source_constraint="C-qc-crosstalk",
        target_constraint="C-qc-transport",
        resolve_fn=ResolveFn.COMPARE,
        description=(
            "α scales idle cost relative to transfer cost in keep-vs-move. "
            "α=1.0 means '1 crosstalk exposure = 1 atom transfer in cost'. "
            "α ∈ [0.5, 2.0] is a flat 'dead zone' — fidelity unchanged. "
            "α=5.0 causes fidelity to drop.  This confirms α=1.0 is near-optimal "
            "for default hardware, but SHOULD be hardware-conditioned."
        ),
        default_strategy="α = 1.0",
        alternative_strategy="Hardware-adaptive α(f_tr, f_xtalk, T2)",
        zap_location="placer.py: idle cost computation",
    ),
}


def list_bridges() -> list[Bridge]:
    """Return all registered bridges."""
    return list(BRIDGES.values())


def get_bridge(bridge_id: str) -> Bridge | None:
    """Get a bridge by ID."""
    return BRIDGES.get(bridge_id)


def high_sensitivity_bridges() -> list[Bridge]:
    """Return bridges that showed non-zero Δ in experiments."""
    return [b for b in BRIDGES.values() if b.id == "BR-keep-vs-move"]


def low_sensitivity_bridges() -> list[Bridge]:
    """Return bridges that showed Δ=0 in experiments."""
    return [b for b in BRIDGES.values() if b.id != "BR-keep-vs-move"]
