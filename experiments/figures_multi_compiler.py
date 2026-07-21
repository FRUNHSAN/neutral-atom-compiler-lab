#!/usr/bin/env python3
"""
figures_multi_compiler.py — Generate Fig.7/9/10/11 style comparison charts
from multi_compiler_results.json.

Produces:
    fig7_zap_vs_zac.png       — Fidelity breakdown for ZAP vs ZAC (all 14 TQE benchmarks)
    fig9_compiler_losses.png  — Compiler-dependent fidelity losses only
    fig10_execution_time.png  — Circuit execution time comparison
    fig11_compile_time.png    — Compilation time comparison
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TQE_ORDER = [
    "adder_n4", "qaoa_n6", "qft_n10", "sat_n11", "bv_n14",
    "multiplier_n15", "qnn_n15", "vqc_n15", "qram_n20",
    "knn_n25", "ising_n26", "wstate_n27", "ghz_n30", "cat_n35",
]

COMPILER_COLORS = {
    "ZAP": "#2ca02c",        # green
    "ZAC": "#ff7f0e",        # orange
    "PowerMove": "#1f77b4",  # blue
    "Enola": "#d62728",      # red
}

COMPILER_HATCH = {
    "ZAP": "",
    "ZAC": "//",
    "PowerMove": "..",
    "Enola": "xx",
}


def load_results():
    path = PROJECT_ROOT / "application" / "multi_compiler_results.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run multi_compiler_compare.py first.")
        sys.exit(1)
    return json.loads(path.read_text())


def pivot(results, field, compilers=None):
    """Build {benchmark: {compiler: value}} dict."""
    data = {}
    for r in results:
        bm = r["benchmark"]
        comp = r["compiler"]
        if compilers and comp not in compilers:
            continue
        data.setdefault(bm, {})[comp] = r.get(field, 0)
    return data


# ═══════════════════════════════════════════════════════════════════
#  Fig.7: Fidelity breakdown — stacked bars, ZAP vs ZAC (14 benchmarks)
# ═══════════════════════════════════════════════════════════════════

def fig7_fidelity_breakdown(results):
    """ZAP vs ZAC stacked fidelity breakdown on all 14 TQE benchmarks."""
    compilers = ["ZAP", "ZAC"]
    benchmarks = [b for b in TQE_ORDER if any(
        r["benchmark"] == b and r["compiler"] in compilers for r in results
    )]

    fig, axes = plt.subplots(1, 2, figsize=(20, 8), sharey=True)

    for ci, compiler in enumerate(compilers):
        ax = axes[ci]

        f_2q_vals, f_idle_vals, f_tr_vals, f_dec_vals = [], [], [], []
        for bm in benchmarks:
            recs = [r for r in results if r["benchmark"] == bm and r["compiler"] == compiler]
            if not recs:
                f_2q_vals.extend([0, 0, 0, 0])
                continue
            r = recs[0]
            f2q = r["f_2q"]
            fid = r["f_idle"]
            ftr = r["f_tr"]
            fdec = r["f_dec"]

            # Build stacked values
            base = f2q
            idle_contrib = base * fid - base
            tr_contrib = base * fid * ftr - base * fid
            dec_contrib = base * fid * ftr * fdec - base * fid * ftr

            f_2q_vals.append(base)
            f_idle_vals.append(idle_contrib)
            f_tr_vals.append(tr_contrib)
            f_dec_vals.append(dec_contrib)

        x = np.arange(len(benchmarks))
        width = 0.7

        colors = ["#2ca02c", "#ff7f0e", "#d62728", "#1f77b4"]
        labels = ["2q gates", "Idle/Crosstalk", "Atom Transfer", "Decoherence"]

        bottom = np.zeros(len(benchmarks))
        for i, (vals, color, label) in enumerate(zip(
            [f_2q_vals, f_idle_vals, f_tr_vals, f_dec_vals], colors, labels
        )):
            ax.bar(x, vals, width, bottom=bottom, color=color, label=label,
                   alpha=0.85, edgecolor="white", linewidth=0.3)
            bottom = bottom + np.array(vals)

        # F_wo_1q line
        f_wo = [r["f_2q"] * r["f_idle"] * r["f_tr"] * r["f_dec"]
                for bm in benchmarks
                for r in [next((rr for rr in results if rr["benchmark"]==bm and rr["compiler"]==compiler), None)]
                if r]
        if len(f_wo) == len(x):
            ax.scatter(x, f_wo, color="black", s=20, zorder=10)

        ax.set_title(f"{compiler}", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([b.replace("_n", "\n") for b in benchmarks],
                           fontsize=7, rotation=45, ha="right")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        if ci == 0:
            ax.set_ylabel("Fidelity (w/o single-qubit gates)", fontsize=11)

    axes[0].legend(loc="lower left", fontsize=8, ncol=2, framealpha=0.9)
    fig.suptitle("Fig.7: Structured-Benchmark Fidelity Breakdown — ZAP vs ZAC (14 TQE benchmarks)\n"
                 "PowerMove shown on compatible benchmarks only",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    out = PROJECT_ROOT / "application" / "figures" / "fig7_zap_vs_zac.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig.7: {out}")


# ═══════════════════════════════════════════════════════════════════
#  Fig.9: Compiler-dependent fidelity losses only
# ═══════════════════════════════════════════════════════════════════

def fig9_compiler_losses(results):
    """Compiler-dependent losses (F_tr × F_dec × F_idle), excluding F_2q."""
    compilers = ["ZAP", "ZAC"]
    # Only show benchmarks where both compilers have data
    benchmarks = [b for b in TQE_ORDER if all(
        any(r["benchmark"]==b and r["compiler"]==c for r in results) for c in compilers
    )]

    fig, ax = plt.subplots(figsize=(16, 7))

    x = np.arange(len(benchmarks))
    width = 0.32

    for ci, compiler in enumerate(compilers):
        vals = []
        for bm in benchmarks:
            rec = next((r for r in results if r["benchmark"]==bm and r["compiler"]==compiler), None)
            if rec:
                f_compiler = rec["f_idle"] * rec["f_tr"] * rec["f_dec"]
                vals.append(f_compiler)
            else:
                vals.append(0)

        offset = (ci - 0.5) * width
        color = COMPILER_COLORS.get(compiler, "#888")
        hatch = COMPILER_HATCH.get(compiler, "")
        ax.bar(x + offset, vals, width, label=compiler, color=color,
               alpha=0.8, edgecolor="white", linewidth=0.5, hatch=hatch)

    ax.set_xticks(x)
    ax.set_xticklabels([b.replace("_n", "\n") for b in benchmarks],
                       fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("Compiler-dependent Fidelity (F_idle × F_tr × F_dec)", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(fontsize=10, framealpha=0.9)
    ax.set_title("Fig.9: Compiler-Dependent Fidelity Losses — ZAP vs ZAC\n"
                 "(gate-infidelity terms omitted for clarity, matching paper §VII.A)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = PROJECT_ROOT / "application" / "figures" / "fig9_compiler_losses.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig.9: {out}")


# ═══════════════════════════════════════════════════════════════════
#  Fig.10 + Fig.11: Execution time + Compilation time
# ═══════════════════════════════════════════════════════════════════

def fig10_11_timing(results):
    """Execution time (Fig.10) + Compilation time (Fig.11)."""
    compilers = ["ZAP", "ZAC", "PowerMove"]
    benchmarks = [b for b in TQE_ORDER if any(
        r["benchmark"]==b and r["compiler"] in compilers for r in results
    )]
    # Limit to first 10 for readability
    benchmarks = benchmarks[:10]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    x = np.arange(len(benchmarks))
    width = 0.25

    for ci, compiler in enumerate(compilers):
        exec_vals, comp_vals = [], []
        for bm in benchmarks:
            rec = next((r for r in results if r["benchmark"]==bm and r["compiler"]==compiler), None)
            if rec:
                exec_vals.append(rec.get("total_duration_us", 0))
                comp_vals.append(rec.get("compilation_time_s", 0))
            else:
                exec_vals.append(0)
                comp_vals.append(0)

        offset = (ci - 1) * width
        color = COMPILER_COLORS.get(compiler, "#888")

        ax1.bar(x + offset, exec_vals, width, label=compiler, color=color,
                alpha=0.8, edgecolor="white", linewidth=0.3)
        ax2.bar(x + offset, comp_vals, width, label=compiler, color=color,
                alpha=0.8, edgecolor="white", linewidth=0.3)

    ax1.set_xticks(x)
    ax1.set_xticklabels([b.replace("_n", "\n") for b in benchmarks],
                        fontsize=7, rotation=45, ha="right")
    ax1.set_ylabel("Execution Time (us)", fontsize=11)
    ax1.set_title("Fig.10: Circuit Execution Time", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    ax1.legend(fontsize=9)

    ax2.set_xticks(x)
    ax2.set_xticklabels([b.replace("_n", "\n") for b in benchmarks],
                        fontsize=7, rotation=45, ha="right")
    ax2.set_ylabel("Compilation Time (s)", fontsize=11)
    ax2.set_yscale("log")
    ax2.set_title("Fig.11: Compilation Time (log scale)", fontsize=12, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3, linestyle="--")
    ax2.legend(fontsize=9)

    fig.suptitle("Circuit Execution & Compilation Time — ZAP vs ZAC vs PowerMove",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = PROJECT_ROOT / "application" / "figures" / "fig10_11_timing.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig.10+11: {out}")


# ═══════════════════════════════════════════════════════════════════
#  Summary table
# ═══════════════════════════════════════════════════════════════════

def print_summary_table(results):
    """Print a comprehensive comparison table."""
    compilers = sorted(set(r["compiler"] for r in results))
    print()
    print("=" * 110)
    print("  Full Comparison: ZAP vs ZAC vs PowerMove")
    print("=" * 110)
    header = f"{'Benchmark':<18}"
    for c in compilers:
        header += f" {c+' F':>9} {c+' F_tr':>8} {c+' Comp(s)':>10}"
    print(header)
    print("-" * 110)

    for bm in TQE_ORDER:
        line = f"{bm:<18}"
        for c in compilers:
            rec = next((r for r in results if r["benchmark"]==bm and r["compiler"]==c), None)
            if rec:
                line += f" {rec['f_total']:>9.4f} {rec['f_tr']:>8.4f} {rec['compilation_time_s']:>10.3f}"
            else:
                line += f" {'—':>9} {'—':>8} {'—':>10}"
        print(line)
    print("-" * 110)
    print()


def main():
    results = load_results()
    print(f"Loaded {len(results)} results across "
          f"{len(set(r['compiler'] for r in results))} compilers × "
          f"{len(set(r['benchmark'] for r in results))} benchmarks")
    print()

    print_summary_table(results)

    # Generate figures
    fig7_fidelity_breakdown(results)
    fig9_compiler_losses(results)
    fig10_11_timing(results)

    print()
    print("  Done. All figures in application/figures/")
    print()
    print("  Caveats:")
    print("    - ZAC F_2q may differ from ZAP due to double-transpilation")
    print("      → Fig.9 uses compiler-dependent channels only (F_idle×F_tr×F_dec)")
    print("    - PowerMove: only 4/14 benchmarks (graph_coloring bug on irregular topologies)")
    print("    - Enola: excluded (too slow, >180s/benchmark)")
    print("    - ZAC f_idle reported as 1.0 (crosstalk code commented out in ZAC simulator)")


if __name__ == "__main__":
    main()
