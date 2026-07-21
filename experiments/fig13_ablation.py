#!/usr/bin/env python3
"""
fig13_ablation.py — ZAP Fig.13 reproduction: idle qubit policy ablation.

Runs ZAP with three idle qubit policies (always_move, always_stay, lookahead)
on all TQE benchmarks and compares:
  - Top panel: fidelity breakdown (F_2q, F_idle, F_tr, F_dec)
  - Bottom panel: circuit execution time (total_duration, total_movement_duration)

Usage:
    python experiments/fig13_ablation.py              # run all + generate chart
    python experiments/fig13_ablation.py --cached     # use cached results only
    python experiments/fig13_ablation.py --benchmark qram_n20  # single benchmark

Paper reference:
    ZAP Fig.13: "Ablation study: idle qubit keep/move policy comparison"
    Three policies compared on fidelity breakdown + runtime.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZAP_ROOT = PROJECT_ROOT / "baselines" / "neutral-atom-compilation"
RESULTS_DIR = ZAP_ROOT / "results" / "fig13_ablation"

# ── Policies ─────────────────────────────────────────────────────
POLICIES = [
    ("always_move",  "Always Move",  "#d62728"),   # red — move all idle qubits to storage
    ("always_stay",  "Always Stay",  "#1f77b4"),   # blue — keep all idle qubits in EZ
    ("lookahead",    "Dynamic (ZAP)","#2ca02c"),   # green — paper's Eq.15 per-qubit decision
]

# ── TQE benchmarks ───────────────────────────────────────────────
TQE_BENCHMARKS = [
    "adder_n4", "qaoa_n6", "qft_n10", "sat_n11", "bv_n14",
    "multiplier_n15", "qnn_n15", "vqc_n15", "qram_n20",
    "knn_n25", "ising_n26", "wstate_n27", "ghz_n30", "cat_n35",
]

# ── Highlighted benchmarks for paper-style display ────────────────
# Paper calls out QRAM, KNN, VQC as interesting cases
HIGHLIGHT = {"qram_n20", "knn_n25", "vqc_n15", "multiplier_n15",
             "qft_n10", "ghz_n30"}


def run_zap_benchmark(benchmark, policy):
    """Run ZAP on a single benchmark with a specific idle qubit policy.

    Returns (fidelity_record, duration_s) or (None, None) on failure.
    """
    # Build a temporary setting JSON for a single benchmark
    import tempfile
    setting = {
        "benchmark": [f"tqe/{benchmark}.qasm"],
        "type": "qasm",
        "architecture": "default.json",
        "routing_cfg": {
            "parallel_priority_weight": 1000.0,
            "initial_mapping_parallel_lookahead": 0,
        },
        "simulation": True,
        "animation": False,
        "output_dir": f"fig13_ablation/{policy}/{benchmark}",
    }

    tmp_path = ZAP_ROOT / "setting" / f"_fig13_{policy}_{benchmark}.json"
    with open(tmp_path, "w") as f:
        json.dump(setting, f)

    routing_flag = policy
    if policy == "lookahead":
        routing_flag = "baseline"  # ZAP's "baseline" IS Eq.15 lookahead
    # Note: always_move / always_stay are the forced policies

    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "run.py", f"_fig13_{policy}_{benchmark}",
         "--routing_strategy", routing_flag],
        cwd=str(ZAP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = time.time() - t0

    # Clean up temp setting
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        return None, None

    # Load the result JSON
    log_dir = ZAP_ROOT / "results" / f"fig13_ablation" / policy / benchmark / "log"
    json_files = sorted(log_dir.glob("*.json")) if log_dir.exists() else []
    if not json_files:
        return None, None

    data = json.loads(json_files[-1].read_text())
    rec = data[-1] if isinstance(data, list) else data

    return rec, elapsed


def load_cached_results():
    """Load all cached ablation results from disk."""
    records = {}  # {benchmark: {policy: rec}}
    if not RESULTS_DIR.exists():
        return records

    for policy_dir in RESULTS_DIR.iterdir():
        if not policy_dir.is_dir():
            continue
        policy = policy_dir.name
        if policy not in {p[0] for p in POLICIES}:
            continue

        for bench_dir in policy_dir.iterdir():
            if not bench_dir.is_dir():
                continue
            benchmark = bench_dir.name
            log_dir = bench_dir / "log"
            json_files = sorted(log_dir.glob("*.json")) if log_dir.exists() else []
            if not json_files:
                continue
            data = json.loads(json_files[-1].read_text())
            rec = data[-1] if isinstance(data, list) else data
            records.setdefault(benchmark, {})[policy] = rec

    return records


def run_all(selected_benchmarks):
    """Run all policy × benchmark combinations. Slow (~14 × 3 = 42 runs)."""
    n_total = len(selected_benchmarks) * len(POLICIES)
    n_done = 0

    for i, benchmark in enumerate(selected_benchmarks):
        for policy_key, policy_name, _ in POLICIES:
            n_done += 1
            print(f"  [{n_done}/{n_total}] {benchmark} @ {policy_name}...", end=" ", flush=True)

            rec, elapsed = run_zap_benchmark(benchmark, policy_key)
            if rec is not None:
                fid = rec.get("total_fidelity", 0)
                dur = rec.get("total_duration", 0)
                print(f"F={fid:.4f}  dur={dur:.1f}us  ({elapsed:.1f}s)")
            else:
                print(f"FAILED")

    print(f"  Done: {n_done}/{n_total} runs")


def compute_metrics(rec):
    """Extract fidelity and timing metrics from a ZAP result record."""
    f_2q = rec.get("fidelity_2q_gate", 1.0)
    f_idle = rec.get("fidelity_idle", 1.0)
    f_tr = rec.get("fidelity_handover", 1.0)
    f_dec = rec.get("fidelity_decoherence", 1.0)

    # Paper convention: exclude single-qubit gate fidelity (§VII.A)
    f_wo_1q = f_2q * f_idle * f_tr * f_dec

    return {
        "f_total": rec.get("total_fidelity", 0),
        "f_wo_1q": f_wo_1q,
        "f_2q": f_2q,
        "f_idle": f_idle,
        "f_tr": f_tr,
        "f_dec": f_dec,
        "total_duration": rec.get("total_duration", 0),
        "stages": rec.get("stage", 0),
        "n_2q": rec.get("n_2q_gate", 0),
    }


def print_table(records):
    """Print comparison table for all benchmarks."""
    print()
    print("=" * 120)
    print("  Fig.13 Ablation: Idle Qubit Policy Comparison")
    print("=" * 120)
    header = (f"{'Benchmark':<18} {'Policy':<18} "
              f"{'F_wo_1q':>10} {'F_2q':>10} {'F_idle':>10} "
              f"{'F_tr':>10} {'F_dec':>10} {'Dur(us)':>10} {'Stages':>7}")
    print(header)
    print("-" * 120)

    for benchmark in TQE_BENCHMARKS:
        if benchmark not in records:
            continue
        for policy_key, policy_name, _ in POLICIES:
            if policy_key not in records[benchmark]:
                continue
            m = compute_metrics(records[benchmark][policy_key])
            print(f"{benchmark:<18} {policy_name:<18} "
                  f"{m['f_wo_1q']:>10.4f} {m['f_2q']:>10.4f} {m['f_idle']:>10.4f} "
                  f"{m['f_tr']:>10.4f} {m['f_dec']:>10.4f} "
                  f"{m['total_duration']:>10.0f} {m['stages']:>7}")

    print("-" * 120)
    print()


def generate_chart(records, output_path):
    """Generate Fig.13-style chart: fidelity breakdown (top) + duration (bottom)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # Select highlighted benchmarks for the main chart
    benchmarks = [b for b in TQE_BENCHMARKS if b in records and b in HIGHLIGHT]
    # Fill remaining with benchmarks that have data from all 3 policies
    remaining = [b for b in TQE_BENCHMARKS
                 if b in records and b not in benchmarks
                 and len(records[b]) == 3]
    # Take a few more to have ~10 benchmarks in the chart
    benchmarks = benchmarks + remaining[:4]
    benchmarks = sorted(set(benchmarks), key=lambda b: TQE_BENCHMARKS.index(b))

    n_bench = len(benchmarks)
    n_policies = len(POLICIES)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                                    gridspec_kw={"height_ratios": [2, 1]})

    x = np.arange(n_bench)
    width = 0.25

    for pi, (policy_key, policy_name, color) in enumerate(POLICIES):
        f_2q_vals, f_idle_vals, f_tr_vals, f_dec_vals = [], [], [], []
        dur_vals = []
        missing = 0

        for bi, benchmark in enumerate(benchmarks):
            if policy_key in records.get(benchmark, {}):
                m = compute_metrics(records[benchmark][policy_key])
                f_2q_vals.append(m["f_2q"])
                f_idle_vals.append(m["f_idle"] * m["f_2q"])  # stack: f_2q then f_idle×f_2q
                f_tr_vals.append(m["f_tr"] * m["f_idle"] * m["f_2q"])
                f_dec_vals.append(m["f_dec"] * m["f_tr"] * m["f_idle"] * m["f_2q"])
                dur_vals.append(m["total_duration"])
            else:
                f_2q_vals.append(0)
                f_idle_vals.append(0)
                f_tr_vals.append(0)
                f_dec_vals.append(0)
                dur_vals.append(0)
                missing += 1

        offset = (pi - 1) * width
        bar_f2q = ax1.bar(x + offset, f_2q_vals, width, label=f"{policy_name} 2q",
                          color=color, alpha=0.85, edgecolor="white", linewidth=0.3)
        bar_idle = ax1.bar(x + offset, [a - b for a, b in zip(f_idle_vals, f_2q_vals)],
                           width, bottom=f_2q_vals, label=f"{policy_name} idle/crosstalk",
                           color=color, alpha=0.45, edgecolor="white", linewidth=0.3,
                           hatch="//")
        bar_tr = ax1.bar(x + offset, [a - b for a, b in zip(f_tr_vals, f_idle_vals)],
                         width, bottom=f_idle_vals, label=f"{policy_name} transfer",
                         color=color, alpha=0.25, edgecolor="white", linewidth=0.3,
                         hatch="..")
        bar_dec = ax1.bar(x + offset, [a - b for a, b in zip(f_dec_vals, f_tr_vals)],
                          width, bottom=f_tr_vals, label=f"{policy_name} decoherence",
                          color=color, alpha=0.12, edgecolor="white", linewidth=0.3,
                          hatch="xx")

        ax2.bar(x + offset, dur_vals, width, color=color, alpha=0.7,
                edgecolor="white", linewidth=0.3)

    ax1.set_ylabel("Fidelity (w/o single-qubit gates)", fontsize=11)
    ax1.set_ylim(0, 1.05)
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    ax1.legend(loc="upper right", ncol=3, fontsize=7, framealpha=0.9)

    ax2.set_ylabel("Execution time (us)", fontsize=11)
    ax2.set_xlabel("Benchmark", fontsize=11)
    ax2.grid(axis="y", alpha=0.3, linestyle="--")

    # X-axis labels
    labels = [b.replace("_n", " (") + ")" for b in benchmarks]
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)

    fig.suptitle("Fig.13 Reproduction: Idle Qubit Policy Ablation\n"
                 "Fidelity breakdown (top) + execution time (bottom)",
                 fontsize=13, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {output_path}")


def main():
    use_cached = "--cached" in sys.argv
    single_benchmark = None
    for arg in sys.argv:
        if arg.startswith("--benchmark="):
            single_benchmark = arg.split("=", 1)[1]

    selected = [single_benchmark] if single_benchmark else TQE_BENCHMARKS

    print("=" * 72)
    print("  ZAP Fig.13: Idle Qubit Policy Ablation")
    print("=" * 72)
    print(f"  Benchmarks: {len(selected)}")
    print(f"  Policies:   {', '.join(p[0] for p in POLICIES)}")
    print()

    if not use_cached:
        run_all(selected)
    else:
        print("  Using cached results (--cached)")

    records = load_cached_results()
    n_bench = len(records)
    total_combos = sum(len(policies) for policies in records.values())
    print(f"\n  Loaded: {n_bench} benchmarks × up to 3 policies = {total_combos} data points")

    if n_bench == 0:
        print("  ERROR: No results found. Run without --cached first.")
        sys.exit(1)

    print_table(records)

    chart_path = PROJECT_ROOT / "application" / "figures" / "fig13_ablation.png"
    if n_bench >= 3:
        generate_chart(records, chart_path)

    # Also export CSV
    csv_path = PROJECT_ROOT / "application" / "fig13_ablation.csv"
    with open(csv_path, "w") as f:
        f.write("benchmark,policy,F_total,F_wo_1q,F_2q,F_idle,F_tr,F_dec,"
                "total_duration,stages,n_2q\n")
        for benchmark in TQE_BENCHMARKS:
            if benchmark not in records:
                continue
            for policy_key, policy_name, _ in POLICIES:
                if policy_key not in records[benchmark]:
                    continue
                m = compute_metrics(records[benchmark][policy_key])
                f.write(f"{benchmark},{policy_name},"
                        f"{m['f_total']:.8f},{m['f_wo_1q']:.8f},"
                        f"{m['f_2q']:.8f},{m['f_idle']:.8f},{m['f_tr']:.8f},{m['f_dec']:.8f},"
                        f"{m['total_duration']:.2f},{m['stages']},{m['n_2q']}\n")
    print(f"  CSV exported: {csv_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
