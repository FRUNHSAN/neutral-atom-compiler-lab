"""
fidelity.py — Cross-compiler fidelity model.

Implements ZAP Eq.4 as a unified fidelity formula across compilers.
Validated against Enola (5/5 PASS) and ZAC (6/6 PASS) built-in simulators.

The model decomposes total fidelity into 5 independent channels:
  F_total = F_1q × F_2q × F_xtalk × F_transfer × F_coherence

This is the ground truth for all bridge swap experiments.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


# ── Default hardware parameters ──────────────────────────
# These match ZAP paper Table I (default architecture).
DEFAULT_PARAMS = {
    "f1": 0.9997,       # single-qubit gate fidelity
    "f2": 0.995,        # two-qubit gate fidelity
    "f2q_idle": 0.9975, # idle qubit crosstalk fidelity (1 - (1-f2)/2)
    "f_tr": 0.999,      # atom transfer fidelity
    "T2": 1.5e6,        # coherence time (microseconds)
}


@dataclass
class ErrorCounts:
    """Per-channel error event counts extracted from a compiler trace."""
    n_1q: int = 0            # single-qubit gate count
    n_2q: int = 0            # two-qubit gate count
    n_idle_exposures: int = 0  # idle qubit × Rydberg stage exposures
    n_transfers: int = 0     # atom activate + deactivate count
    total_idle_time: float = 0.0  # total qubit-idle time (microseconds)
    per_qubit_idle: list[float] = field(default_factory=list)


@dataclass
class FidelityBreakdown:
    """Channel-by-channel fidelity decomposition."""
    f_1q: float = 1.0
    f_2q: float = 1.0
    f_xtalk: float = 1.0
    f_transfer: float = 1.0
    f_coherence: float = 1.0

    @property
    def total(self) -> float:
        return self.f_1q * self.f_2q * self.f_xtalk * self.f_transfer * self.f_coherence

    def as_dict(self) -> dict:
        return {
            "cir_fidelity": self.total,
            "cir_fidelity_1q_gate": self.f_1q,
            "cir_fidelity_2q_gate": self.f_2q,
            "cir_fidelity_2q_gate_for_idle": self.f_xtalk,
            "cir_fidelity_atom_transfer": self.f_transfer,
            "cir_fidelity_coherence": self.f_coherence,
        }


def compute_fidelity(
    counts: ErrorCounts,
    params: dict | None = None,
    *,
    decoherence_model: str = "exponential",
) -> FidelityBreakdown:
    """Compute fidelity breakdown from error channel counts.

    Args:
        counts: ErrorCounts from parsing a compiler trace.
        params: Hardware parameters (defaults to ZAP Table I).
        decoherence_model:
            "exponential" — F_coherence = exp(-t/T2)  [ZAP default]
            "linear"      — F_coherence = ∏(1 - t_q/T2)  [Enola]

    Returns:
        FidelityBreakdown with per-channel values.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    result = FidelityBreakdown()
    result.f_1q = math.pow(p["f1"], counts.n_1q)
    result.f_2q = math.pow(p["f2"], counts.n_2q)
    result.f_xtalk = math.pow(p["f2q_idle"], counts.n_idle_exposures)
    result.f_transfer = math.pow(p["f_tr"], counts.n_transfers)

    T2 = p["T2"]
    if decoherence_model == "exponential":
        result.f_coherence = math.exp(-counts.total_idle_time / T2)
    else:
        result.f_coherence = 1.0
        for t_q in counts.per_qubit_idle:
            result.f_coherence *= (1.0 - t_q / T2)

    return result


def compare_fidelity(
    ours: FidelityBreakdown,
    theirs: dict,
    tolerance: float = 0.001,
) -> dict[str, bool]:
    """Compare two fidelity breakdowns channel-by-channel.

    Args:
        ours: Framework-computed FidelityBreakdown.
        theirs: Dict with keys matching as_dict() output (e.g. from compiler's built-in sim).
        tolerance: Absolute difference threshold for PASS.

    Returns:
        Dict of channel_name → pass/fail.
    """
    our_dict = ours.as_dict()
    results = {}
    for key in our_dict:
        diff = abs(our_dict[key] - theirs.get(key, 0.0))
        results[key] = diff < tolerance
    return results
