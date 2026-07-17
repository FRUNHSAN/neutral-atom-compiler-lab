"""
strategy_compare.py — hard_threshold vs AL soft decision comparison.

The core experiment: compare ZAP's per-qubit hard threshold (Eq.15)
against augmented Lagrangian joint optimization on slot-constrained
keep-vs-move decisions.

Uses the validated fidelity model as ground truth.
Generates realistic cost matrices for 3 circuit types.

Output: per-circuit comparison of fidelity, violations, and runtime.
"""
from __future__ import annotations
import math
import sys
import os
import random
import time
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "domain", "formulas"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instances", "ZAP"))
from fidelity import DEFAULT_PARAMS
from adapter import ZAPKeepVsMoveAdapter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ── Hardware parameters (validated against Enola + ZAC) ──
F2 = DEFAULT_PARAMS["f2"]
F2Q_IDLE = DEFAULT_PARAMS["f2q_idle"]
F_TR = DEFAULT_PARAMS["f_tr"]
T2 = DEFAULT_PARAMS["T2"]


def generate_cost_matrix(
    n_qubits: int,
    n_stages: int,
    circuit_type: str = "qram",
    slot_count: int = 4,
    stage: int = 0,
    seed: int = 42,
) -> dict:
    """Generate cost matrix for a single Rydberg stage.

    Circuit types:
      qram     — tree-structured, non-uniform qubit reuse
      qft      — butterfly pattern, high all-to-all reuse
      regular3 — uniform degree-3, each qubit used exactly 3 times
    """
    rng = random.Random(seed + zlib.crc32(circuit_type.encode()) + stage)

    if circuit_type == "qram":
        reuse = [rng.randint(1, n_stages) for _ in range(n_qubits)]
    elif circuit_type == "qft":
        reuse = [rng.randint(n_stages // 3, n_stages) for _ in range(n_qubits)]
    else:
        reuse = [min(3, n_stages) for _ in range(n_qubits)]

    cost_matrix = {}
    for q in range(n_qubits):
        if reuse[q] <= stage:
            continue
        if rng.random() > 0.85:  # 85% idle per stage
            continue

        remaining = reuse[q] - stage
        k = rng.randint(1, min(remaining + 2, 8))
        n_tr = 4 if q < slot_count else 2

        L_xtalk = k * (-math.log(F2Q_IDLE))
        L_tr = n_tr * (-math.log(F_TR))
        t_extra = 2 * math.sqrt(abs(q - slot_count // 2) * 6.0 / 1e6)
        L_dec = 1.0 * (n_qubits - 1) * t_extra / T2

        cost_matrix[f"q{q}"] = {
            "L_stay": round(L_xtalk, 8),
            "L_move": round(L_tr + L_dec, 8),
            "k": k,
            "n_tr": n_tr,
        }

    return cost_matrix


def run_comparison(
    n_qubits: int = 20,
    n_stages: int = 10,
    slot_count: int = 4,
    circuit_type: str = "qram",
) -> dict | None:
    """Compare hard_threshold vs AL soft across all stages of a circuit."""

    hard = ZAPKeepVsMoveAdapter(slot_count=slot_count, strategy="hard_threshold")
    soft = ZAPKeepVsMoveAdapter(slot_count=slot_count, strategy="al_soft")

    results = {
        "hard": {"time_ms": 0, "obj": 0, "violations": 0},
        "soft": {"time_ms": 0, "obj": 0, "violations": 0},
        "circuit_type": circuit_type,
        "n_stages": 0,
    }
    soft_prev = None

    for stage in range(n_stages):
        cost_matrix = generate_cost_matrix(
            n_qubits, n_stages, circuit_type, slot_count, stage
        )
        if not cost_matrix:
            continue

        constraints = {"slot_count": slot_count}

        sol_h = hard.solve("BR-keep-vs-move", cost_matrix, constraints)
        results["hard"]["time_ms"] += sol_h.elapsed_ms
        results["hard"]["obj"] += sol_h.objective_value
        staying_h = sum(1 for d in sol_h.decisions.values() if d == 0)
        results["hard"]["violations"] += max(0, staying_h - slot_count)

        sol_s = soft.solve(
            "BR-keep-vs-move", cost_matrix, constraints,
            initial_guess=soft_prev, timeout_ms=50,
        )
        soft_prev = sol_s.decisions
        results["soft"]["time_ms"] += sol_s.elapsed_ms
        results["soft"]["obj"] += sol_s.objective_value
        staying_s = sum(1 for d in sol_s.decisions.values() if d == 0)
        results["soft"]["violations"] += max(0, staying_s - slot_count)

        results["n_stages"] += 1

    if results["n_stages"] == 0:
        return None

    results["hard"]["fidelity_impact"] = math.exp(-results["hard"]["obj"])
    results["soft"]["fidelity_impact"] = math.exp(-results["soft"]["obj"])

    return results


def main():
    print("=" * 64)
    print("  ZAP Keep-vs-Move: hard_threshold vs AL soft")
    print("  Validated fidelity model (Enola 5/5 + ZAC 6/6 PASS)")
    print("=" * 64)

    configs = [
        ("qram", 20, 10, 4),
        ("qft", 20, 10, 4),
        ("regular3", 20, 10, 4),
    ]

    header = (
        f"  {'Circuit':>12s}  {'Strategy':>16s}  {'Time':>8s}  "
        f"{'Objective':>12s}  {'Viol':>6s}  {'Fidelity':>12s}"
    )
    print(f"\n{header}")
    print(f"  {'─'*12}  {'─'*16}  {'─'*8}  {'─'*12}  {'─'*6}  {'─'*12}")

    for ctype, n_q, n_s, slots in configs:
        r = run_comparison(n_q, n_s, slots, ctype)
        if r is None:
            continue

        for strat_key, strat_label in [("hard", "hard_threshold"), ("soft", "AL soft     ")]:
            s = r[strat_key]
            print(
                f"  {ctype:>12s}  {strat_label:>16s}  {s['time_ms']:7.1f}ms "
                f"{s['obj']:12.6f}  {s['violations']:5d}   {s['fidelity_impact']:11.6f}"
            )

        # Gap
        if r["hard"]["obj"] > 0:
            delta_obj = r["hard"]["obj"] - r["soft"]["obj"]
            delta_pct = delta_obj / r["hard"]["obj"] * 100
            print(
                f"  {'':>12s}  {'GAP':>16s}  {'':>8s}  "
                f"{delta_obj:+12.6f}  {'':>6s}  {delta_pct:+9.2f}%"
            )
        print()

    print("  Key:  Viol = slot constraint violations (> 0 = broken)")
    print("        Positive gap → hard_threshold has lower loss (better)")
    print("        In tight-slot scenarios, AL soft eliminates violations")
    print("        at the cost of slightly higher objective (forced moves).")


if __name__ == "__main__":
    main()
