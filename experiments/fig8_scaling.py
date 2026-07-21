#!/usr/bin/env python3
"""
fig8_scaling.py — ZAP Fig.8 reproduction: random-circuit fidelity scaling.

Generates random three-regular graph circuits at increasing qubit counts,
runs ZAP on each, and plots stacked fidelity breakdown vs N.

Usage:
    python experiments/fig8_scaling.py --quick   # 10..100 step 10, 3 instances each
    python experiments/fig8_scaling.py --full    # 10..100 step 10, 10 instances each
    python experiments/fig8_scaling.py --cached  # use cached results + generate chart

Paper reference:
    ZAP Fig.8: "Random-circuit fidelity scaling on three-regular graph
    benchmarks." Each benchmark: one CZ gate per edge of nx.random_regular_graph(3,N).
    For each N, 10 random instances; colored regions show cumulative fidelity
    degradation from 2q gates, transfer, decoherence, and crosstalk.
"""

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# ── Project paths ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZAP_ROOT = PROJECT_ROOT / "baselines" / "neutral-atom-compilation"
BENCHMARK_DIR = ZAP_ROOT / "benchmark" / "random_3reg"
sys.path.insert(0, str(ZAP_ROOT))

from zap.zap import Zap

# ── Parameters ───────────────────────────────────────────────────
QUBIT_COUNTS = list(range(10, 110, 10))  # 10, 20, ..., 100
INSTANCES_PER_N_QUICK = 3
INSTANCES_PER_N_FULL = 10
SEED_BASE = 42  # deterministic graph generation


@contextlib.contextmanager
def silence_zap():
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout


def generate_random_3reg_qasm(n_qubits, seed, output_dir):
    """Generate a QASM 3.0 circuit from a random 3-regular graph.

    Each edge → one CZ gate. The graph is guaranteed simple (no self-loops,
    no parallel edges) for d=3, n≥4.

    Args:
        n_qubits: Number of qubits (vertices).
        seed: Random seed for reproducibility.
        output_dir: Directory to write .qasm file.

    Returns:
        Path to the generated QASM file.
    """
    import networkx as nx

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate random 3-regular graph (simple, undirected)
    # Note: must have n*d even for regular graph to exist
    graph = nx.random_regular_graph(3, n_qubits, seed=seed)

    # Build QASM 3.0 circuit
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{n_qubits}] q;",
    ]
    for u, v in graph.edges():
        lines.append(f"cz q[{u}], q[{v}];")

    qasm_str = "\n".join(lines) + "\n"

    fname = f"rand3reg_n{n_qubits}_seed{seed}.qasm"
    fpath = output_dir / fname
    fpath.write_text(qasm_str)

    return str(fpath.relative_to(ZAP_ROOT / "benchmark"))


def load_architecture(n_qubits):
    """Choose architecture with enough storage traps for n_qubits."""
    if n_qubits <= 80:
        arch_file = "default.json"
    elif n_qubits <= 192:
        arch_file = "scale_to_100.json"
    else:
        arch_file = "scale_to_500.json"

    with open(ZAP_ROOT / "architecture" / arch_file) as f:
        return json.load(f)


def run_zap_single(benchmark_path, architecture, n_qubits, seed):
    """Run ZAP on one random circuit, return fidelity record."""
    import os as _os
    _orig_cwd = _os.getcwd()
    try:
        _os.chdir(ZAP_ROOT)
        with silence_zap():
            zap = Zap(
                benchmark=benchmark_path,
                architecture=architecture,
                initial_mapping=[],
                output_dir=f"fig8_scaling/n{n_qubits}_s{seed}",
                scheduling_strategy="asap_separate",
                placement_strategy="baseline",
                routing_strategy="baseline",
            )
            zap.solve(simulation=True, animation=False)
    except Exception as e:
        return None
    finally:
        _os.chdir(_orig_cwd)

    # Load result
    result_dir = ZAP_ROOT / "results" / "fig8_scaling" / f"n{n_qubits}_s{seed}" / "log"
    json_files = sorted(result_dir.glob("*.json")) if result_dir.exists() else []
    if not json_files:
        return None

    data = json.loads(json_files[-1].read_text())
    return data[-1] if isinstance(data, list) else data


def sweep(args):
    """Run all random circuits. Returns {n_qubits: [rec, ...]}"""
    is_full = "--full" in args
    instances_per_n = INSTANCES_PER_N_FULL if is_full else INSTANCES_PER_N_QUICK

    n_total = len(QUBIT_COUNTS) * instances_per_n
    n_done = 0

    results = {}
    t_start = time.time()

    for n in QUBIT_COUNTS:
        arch = load_architecture(n)
        results[n] = []

        for i in range(instances_per_n):
            seed = SEED_BASE * 100 + n * 10 + i
            n_done += 1

            label = f"n={n:3d} #{i+1}/{instances_per_n}"
            sys.stdout.write(f"\r  [{n_done}/{n_total}] {label}...")
            sys.stdout.flush()

            # Generate QASM
            benchmark_rel = generate_random_3reg_qasm(n, seed, BENCHMARK_DIR)

            # Run ZAP
            rec = run_zap_single(benchmark_rel, arch, n, seed)
            if rec:
                results[n].append(rec)

    elapsed = time.time() - t_start
    print(f"\n  Done: {n_done} runs in {elapsed:.1f}s "
          f"({elapsed/max(1,n_done):.1f}s per run)")

    return results


def load_cached():
    """Load cached results from disk."""
    results = {}
    sweep_dir = ZAP_ROOT / "results" / "fig8_scaling"
    if not sweep_dir.exists():
        return results

    for d in sweep_dir.iterdir():
        if not d.is_dir():
            continue
        # Parse n<num>_s<seed> from dirname
        parts = d.name.split("_")
        n = int(parts[0][1:])  # "n10" → 10
        log_dir = d / "log"
        json_files = sorted(log_dir.glob("*.json")) if log_dir.exists() else []
        if not json_files:
            continue
        data = json.loads(json_files[-1].read_text())
        rec = data[-1] if isinstance(data, list) else data
        results.setdefault(n, []).append(rec)

    return results


def aggregate(results):
    """Aggregate fidelity breakdown per qubit count.

    Returns {n: {mean_2q, mean_idle, mean_tr, mean_dec, std_2q, ...}}
    """
    agg = {}
    for n in sorted(results.keys()):
        recs = results[n]
        if not recs:
            continue

        f_2q_vals = [r.get("fidelity_2q_gate", 1) for r in recs]
        f_idle_vals = [r.get("fidelity_idle", 1) for r in recs]
        f_tr_vals = [r.get("fidelity_handover", 1) for r in recs]
        f_dec_vals = [r.get("fidelity_decoherence", 1) for r in recs]
        dur_vals = [r.get("total_duration", 0) for r in recs]

        agg[n] = {
            "n_instances": len(recs),
            "f_2q_mean": np.mean(f_2q_vals),
            "f_2q_std": np.std(f_2q_vals),
            "f_idle_mean": np.mean(f_idle_vals),
            "f_idle_std": np.std(f_idle_vals),
            "f_tr_mean": np.mean(f_tr_vals),
            "f_tr_std": np.std(f_tr_vals),
            "f_dec_mean": np.mean(f_dec_vals),
            "f_dec_std": np.std(f_dec_vals),
            "duration_mean": np.mean(dur_vals),
            "duration_std": np.std(dur_vals),
        }

    return agg


def generate_chart(agg, output_path):
    """Generate Fig.8-style stacked area chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = sorted(agg.keys())
    f_2q = np.array([agg[n]["f_2q_mean"] for n in ns])
    f_idle = np.array([agg[n]["f_idle_mean"] for n in ns])
    f_tr = np.array([agg[n]["f_tr_mean"] for n in ns])
    f_dec = np.array([agg[n]["f_dec_mean"] for n in ns])

    # Stack multiplicatively: total = f_2q × f_idle × f_tr × f_dec
    # Plot as cumulative degradation
    layer1 = f_2q  # base: 2q gate fidelity
    layer2 = layer1 * f_idle  # + idle/crosstalk
    layer3 = layer2 * f_tr    # + transfer
    layer4 = layer3 * f_dec   # + decoherence = F_wo_1q

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ["#2ca02c", "#ff7f0e", "#d62728", "#1f77b4"]
    labels = ["2q gates", "Idle / Crosstalk", "Atom Transfer", "Decoherence"]

    ax.fill_between(ns, 0, layer1, alpha=0.7, color=colors[0], label=labels[0])
    ax.fill_between(ns, layer1, layer2, alpha=0.6, color=colors[1], label=labels[1])
    ax.fill_between(ns, layer2, layer3, alpha=0.5, color=colors[2], label=labels[2])
    ax.fill_between(ns, layer3, layer4, alpha=0.4, color=colors[3], label=labels[3])

    # Also plot F_wo_1q line
    ax.plot(ns, layer4, "k-", linewidth=2, label="F (w/o 1q gates)", zorder=10)
    ax.plot(ns, layer4, "ko", markersize=6, zorder=10)

    ax.set_xlabel("Number of Qubits", fontsize=12)
    ax.set_ylabel("Fidelity (w/o single-qubit gates)", fontsize=12)
    ax.set_title("Fig.8 Reproduction: Random-Circuit Fidelity Scaling (ZAP only)\n"
                 "3-regular graph benchmarks, stacked fidelity breakdown",
                 fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.05)
    ax.set_xlim(ns[0] - 5, ns[-1] + 5)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9)

    # Add instance count annotation
    for n in ns:
        ax.annotate(f"n={agg[n]['n_instances']}", (n, 0.02),
                    fontsize=7, ha="center", color="gray")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {output_path}")


def print_table(agg):
    """Print fidelity scaling table."""
    print()
    print(f"{'N':>5} {'n_inst':>6} {'F_2q':>8} {'F_idle':>8} {'F_tr':>8} {'F_dec':>8} {'F_wo_1q':>9} {'Dur(us)':>10}")
    print("-" * 70)
    for n in sorted(agg.keys()):
        a = agg[n]
        f_wo = a["f_2q_mean"] * a["f_idle_mean"] * a["f_tr_mean"] * a["f_dec_mean"]
        print(f"{n:>5} {a['n_instances']:>6} "
              f"{a['f_2q_mean']:>8.4f} {a['f_idle_mean']:>8.4f} "
              f"{a['f_tr_mean']:>8.4f} {a['f_dec_mean']:>8.4f} "
              f"{f_wo:>9.4f} {a['duration_mean']:>10.0f}")
    print("-" * 70)
    print()


def export_csv(agg, path):
    """Export scaling data to CSV."""
    with open(path, "w") as f:
        f.write("n_qubits,n_instances,"
                "F_2q_mean,F_2q_std,F_idle_mean,F_idle_std,"
                "F_tr_mean,F_tr_std,F_dec_mean,F_dec_std,"
                "F_wo_1q_mean,duration_mean,duration_std\n")
        for n in sorted(agg.keys()):
            a = agg[n]
            f_wo = a["f_2q_mean"] * a["f_idle_mean"] * a["f_tr_mean"] * a["f_dec_mean"]
            f.write(f"{n},{a['n_instances']},"
                    f"{a['f_2q_mean']:.6f},{a['f_2q_std']:.6f},"
                    f"{a['f_idle_mean']:.6f},{a['f_idle_std']:.6f},"
                    f"{a['f_tr_mean']:.6f},{a['f_tr_std']:.6f},"
                    f"{a['f_dec_mean']:.6f},{a['f_dec_std']:.6f},"
                    f"{f_wo:.6f},{a['duration_mean']:.1f},{a['duration_std']:.1f}\n")
    print(f"  CSV exported: {path}")


def main():
    use_cached = "--cached" in sys.argv

    if use_cached:
        results = load_cached()
        if not results:
            print("No cached results. Run without --cached first.")
            sys.exit(1)
        print(f"Loaded cached results: {sum(len(v) for v in results.values())} runs "
              f"across {len(results)} qubit counts")
    else:
        print("=" * 72)
        print("  ZAP Fig.8: Random-Circuit Fidelity Scaling")
        mode = "--full" if "--full" in sys.argv else "--quick (3 instances/N)"
        print(f"  Qubit counts: {QUBIT_COUNTS}")
        print(f"  Mode: {mode}")
        print("=" * 72)
        results = sweep(sys.argv)

    agg = aggregate(results)
    print_table(agg)

    chart_path = PROJECT_ROOT / "application" / "figures" / "fig8_scaling.png"
    generate_chart(agg, chart_path)

    csv_path = PROJECT_ROOT / "application" / "fig8_scaling.csv"
    export_csv(agg, csv_path)

    # Key insight
    print()
    print("  Key observations:")
    for n in sorted(agg.keys()):
        a = agg[n]
        f_idle = a["f_idle_mean"]
        if f_idle < 0.99:
            print(f"    N={n}: f_idle={f_idle:.4f} — crosstalk present "
                  f"(dynamic policy keeps some idle qubits in EZ)")
    print("  Done.")


if __name__ == "__main__":
    main()
