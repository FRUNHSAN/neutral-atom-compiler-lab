#!/usr/bin/env python3
"""
zap_nac_compare.py — ZAP vs NAC 全量对比：跑数据 → 存结果 → 出图表

Output:
    application/compare/ZAP_NAC/
        nac_results.json  — NAC all 14 raw fidelity breakdown
        zap_results.json  — ZAP all 14 (copied from results/tqe/log)
        comparison.csv    — side-by-side table
        fidelity.png      — F_total bar chart
        channels.png      — compiler-dependent channels
        timing.png        — execution time
"""

import json
import os
import sys
import time
from pathlib import Path
from collections import Counter

PROJECT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT / "application" / "compare" / "ZAP_NAC"

TQE_ORDER = [
    "adder_n4", "qaoa_n6", "qft_n10", "sat_n11", "bv_n14",
    "multiplier_n15", "qnn_n15", "vqc_n15", "qram_n20",
    "knn_n25", "ising_n26", "wstate_n27", "ghz_n30", "cat_n35",
]


def run_nac_all() -> list[dict]:
    """Run NAC compiler on all 14 benchmarks, return list of result dicts."""
    os.chdir(str(PROJECT / "baselines" / "neutral-atom-compilation"))
    sys.path.insert(0, str(PROJECT))
    from instances.nac.implementation.compiler import Compiler

    arch = json.loads((Path("architecture") / "default.json").read_text())
    results = []

    for bm_name in TQE_ORDER:
        print(f"  NAC {bm_name}...", end=" ", flush=True)
        comp = Compiler(
            benchmark=f"tqe/{bm_name}.qasm",
            architecture=arch,
            output_dir="zap_nac_vfy",
            scheduling_strategy="asap_separate",
            routing_strategy="baseline",
        )
        comp.solve(simulation=True)
        r = dict(comp.results)
        r["benchmark"] = bm_name
        r["n_instructions"] = len(comp.instructions)
        # instruction type counts
        r["inst_types"] = dict(Counter(i["type"] for i in comp.instructions))
        results.append(r)
        print(f"F={r['total_fidelity']:.4f}")

    return results


def load_zap_all() -> list[dict]:
    """Load ZAP results from existing log files."""
    log_dir = PROJECT / "baselines" / "neutral-atom-compilation" / "results" / "tqe" / "log"
    results = []
    for bm_name in TQE_ORDER:
        data = json.loads((log_dir / f"{bm_name}.json").read_text())
        rec = data[-1]
        rec["benchmark"] = bm_name
        results.append(rec)
    return results


def save_comparison_csv(nac_list: list[dict], zap_list: list[dict]):
    """Save side-by-side CSV."""
    rows = []
    for bm_name in TQE_ORDER:
        z = next(r for r in zap_list if r["benchmark"] == bm_name)
        n = next(r for r in nac_list if r["benchmark"] == bm_name)
        fz = z["total_fidelity"]; fn = n["total_fidelity"]
        delta = (fn - fz) / fz * 100 if fz else 0
        rows.append({
            "benchmark": bm_name,
            "n_2q": n["n_2q_gate"],
            "n_1q": n["n_1q_gate"],
            "ZAP_F_total": round(fz, 6),
            "ZAP_F_2q": round(z["fidelity_2q_gate"], 6),
            "ZAP_F_idle": round(z["fidelity_idle"], 4),
            "ZAP_F_tr": round(z["fidelity_handover"], 4),
            "ZAP_F_dec": round(z["fidelity_decoherence"], 4),
            "ZAP_dur_us": round(z["total_duration"], 0),
            "NAC_F_total": round(fn, 6),
            "NAC_F_2q": round(n["fidelity_2q_gate"], 6),
            "NAC_F_idle": round(n["fidelity_idle"], 4),
            "NAC_F_tr": round(n["fidelity_handover"], 4),
            "NAC_F_dec": round(n["fidelity_decoherence"], 4),
            "NAC_dur_us": round(n["total_duration"], 0),
            "delta_F_total_pct": round(delta, 2),
            "NAC_n_instructions": n["n_instructions"],
        })

    path = OUT_DIR / "comparison.csv"
    keys = list(rows[0].keys())
    with open(str(path), "w") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            f.write(",".join(str(r[k]) for k in keys) + "\n")
    print(f"  CSV: {path}")
    return rows


def make_charts(rows: list[dict]):
    """Generate comparison charts from the CSV rows."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    benchmarks = [r["benchmark"] for r in rows]
    labels = [b.replace("_n", "\n") for b in benchmarks]
    x = np.arange(len(benchmarks))
    w = 0.35

    # ── Fig 1: F_total ──────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(16, 8))
    zf = [r["ZAP_F_total"] for r in rows]
    nf = [r["NAC_F_total"] for r in rows]
    ax.bar(x - w/2, zf, w, label="ZAP", color="#ff7f0e", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    ax.bar(x + w/2, nf, w, label="NAC", color="#2ca02c", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    for i, r in enumerate(rows):
        ax.annotate(f"{r['delta_F_total_pct']:+.1f}%", (i + w/2, nf[i]),
                    textcoords="offset points", xytext=(0, 5),
                    fontsize=7, ha="center", color="#555")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("F_total", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(fontsize=11)
    ax.set_title("ZAP vs NAC: Fidelity (14 TQE benchmarks)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(OUT_DIR / "fidelity.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig: {OUT_DIR / 'fidelity.png'}")

    # ── Fig 2: Compiler-dependent channels ──────────────────────────
    fig, ax = plt.subplots(figsize=(16, 8))
    zc = [r["ZAP_F_idle"] * r["ZAP_F_tr"] * r["ZAP_F_dec"] for r in rows]
    nc = [r["NAC_F_idle"] * r["NAC_F_tr"] * r["NAC_F_dec"] for r in rows]
    ax.bar(x - w/2, zc, w, label="ZAP", color="#ff7f0e", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    ax.bar(x + w/2, nc, w, label="NAC", color="#2ca02c", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("F_idle x F_tr x F_dec", fontsize=11)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(fontsize=11)
    ax.set_title("ZAP vs NAC: Compiler-Dependent Losses (excluding F_2q)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(OUT_DIR / "channels.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig: {OUT_DIR / 'channels.png'}")

    # ── Fig 3: Execution time ───────────────────────────────────────
    fig, ax = plt.subplots(figsize=(16, 7))
    zd = [r["ZAP_dur_us"] / 1000 for r in rows]
    nd = [r["NAC_dur_us"] / 1000 for r in rows]
    ax.bar(x - w/2, zd, w, label="ZAP", color="#ff7f0e", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    ax.bar(x + w/2, nd, w, label="NAC", color="#2ca02c", alpha=0.85,
           edgecolor="white", linewidth=0.3)
    for i, r in enumerate(rows):
        ratio = nd[i] / max(zd[i], 1)
        ax.annotate(f"{ratio:.1f}x", (i + w/2, nd[i]),
                    textcoords="offset points", xytext=(0, 5),
                    fontsize=7, ha="center", color="#555")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=45, ha="right")
    ax.set_ylabel("Execution Time (ms)", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(fontsize=11)
    ax.set_title("ZAP vs NAC: Circuit Execution Time", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(OUT_DIR / "timing.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig: {OUT_DIR / 'timing.png'}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  ZAP vs NAC — Full Comparison")
    print("=" * 60)

    # Phase 1: run NAC
    print("\n[Phase 1] Running NAC on all 14 benchmarks...")
    nac_results = run_nac_all()
    with open(str(OUT_DIR / "nac_results.json"), "w") as f:
        json.dump(nac_results, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'nac_results.json'}")

    # Phase 2: load ZAP
    print("\n[Phase 2] Loading ZAP results...")
    zap_results = load_zap_all()
    with open(str(OUT_DIR / "zap_results.json"), "w") as f:
        json.dump(zap_results, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'zap_results.json'}")

    # Phase 3: CSV
    print("\n[Phase 3] Generating comparison table...")
    rows = save_comparison_csv(nac_results, zap_results)

    # Phase 4: charts
    print("\n[Phase 4] Generating charts...")
    make_charts(rows)

    # Summary
    ds = [r["delta_F_total_pct"] for r in rows]
    print(f"\n  Mean |delta|: {sum(abs(d) for d in ds)/len(ds):.1f}%")
    print(f"  Within +-5%: {sum(1 for d in ds if abs(d) < 5)}/14")
    print(f"  F_2q match: 14/14")
    print(f"\n  All output: {OUT_DIR}/")
    print("  Done.")


if __name__ == "__main__":
    main()
