#!/usr/bin/env python3
"""
fig7_14_nac.py — ZAP vs NAC Fig.7-Fig.14 全套对比图

Output: application/compare/ZAP_NAC/fig7_*.png ... fig14_*.png
"""
import json, os, sys, time, math
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "application" / "compare" / "ZAP_NAC"

TQE = ['adder_n4','qaoa_n6','qft_n10','sat_n11','bv_n14','multiplier_n15',
       'qnn_n15','vqc_n15','qram_n20','knn_n25','ising_n26','wstate_n27',
       'ghz_n30','cat_n35']


def run_nac(benchmark, arch=None, strategy="baseline"):
    os.chdir(str(PROJECT / "baselines" / "neutral-atom-compilation"))
    sys.path.insert(0, str(PROJECT))
    from instances.nac.implementation.compiler import Compiler
    if arch is None:
        arch = json.loads(Path("architecture/default.json").read_text())
    comp = Compiler(benchmark=benchmark, architecture=arch,
                    output_dir="fig_nac", scheduling_strategy="asap_separate",
                    routing_strategy=strategy)
    comp.solve(simulation=True)
    return comp.results


def load_zap(bm):
    log = PROJECT / "baselines/neutral-atom-compilation/results/tqe/log" / f"{bm}.json"
    return json.loads(log.read_text())[-1]


# ═══════════════════════════════════════════════════════════════════
#  Fig.7: Fidelity breakdown — stacked bars, ZAP vs NAC
# ═══════════════════════════════════════════════════════════════════
def fig7():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt; import numpy as np

    # Read CSV manually
    csv_lines = (OUT / "comparison.csv").read_text().strip().split("\n")
    header = csv_lines[0].split(",")
    rows = []
    for line in csv_lines[1:]:
        vals = line.split(",")
        rows.append(dict(zip(header, vals)))
    benchmarks = [r["benchmark"] for r in rows]
    labels = [b.replace("_n","\n") for b in benchmarks]
    x = np.arange(len(benchmarks)); w = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8), sharey=True)

    for ax, compiler in [(ax1, "ZAP"), (ax2, "NAC")]:
        prefix = "ZAP_" if compiler == "ZAP" else "NAC_"
        f2q = [float(r[f"{prefix}F_2q"]) for r in rows]
        fidle = [float(r[f"{prefix}F_idle"]) for r in rows]
        ftr = [float(r[f"{prefix}F_tr"]) for r in rows]
        fdec = [float(r[f"{prefix}F_dec"]) for r in rows]

        base = np.array(f2q)
        ax.bar(x, base, w*2, color="#2ca02c", alpha=0.85, label="2q gates", edgecolor="white", linewidth=0.3)

        idle_contrib = base * np.array(fidle) - base
        ax.bar(x, idle_contrib, w*2, bottom=base, color="#d62728", alpha=0.85, label="Idle/Crosstalk", edgecolor="white", linewidth=0.3)

        tr_base = base * np.array(fidle)
        tr_contrib = tr_base * np.array(ftr) - tr_base
        ax.bar(x, tr_contrib, w*2, bottom=tr_base, color="#ff7f0e", alpha=0.85, label="Atom Transfer", edgecolor="white", linewidth=0.3)

        dec_base = tr_base * np.array(ftr)
        dec_contrib = dec_base * np.array(fdec) - dec_base
        ax.bar(x, dec_contrib, w*2, bottom=dec_base, color="#1f77b4", alpha=0.85, label="Decoherence", edgecolor="white", linewidth=0.3)

        # F_wo_1q dot
        f_wo = tr_base * np.array(fdec)
        ax.scatter(x, f_wo, color="black", s=15, zorder=10)

        ax.set_title(compiler, fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3, linestyle="--")

    ax1.set_ylabel("Fidelity (w/o single-qubit gates)", fontsize=11)
    ax1.legend(loc="lower left", fontsize=8, ncol=2, framealpha=0.9)

    fig.suptitle("Fig.7: Fidelity Breakdown — ZAP vs NAC (14 TQE benchmarks)", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(str(OUT / "fig7_fidelity_breakdown.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  fig7_fidelity_breakdown.png")


# ═══════════════════════════════════════════════════════════════════
#  Fig.9: Compiler-dependent losses (F_idle × F_tr × F_dec)
# ═══════════════════════════════════════════════════════════════════
def fig9():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt; import numpy as np
    # Already have channels.png — regenerate as fig9
    if (OUT / "channels.png").exists():
        import shutil
        shutil.copy(str(OUT / "channels.png"), str(OUT / "fig9_compiler_losses.png"))
        print("  fig9_compiler_losses.png")


# ═══════════════════════════════════════════════════════════════════
#  Fig.10+11: Execution time + Compilation time
# ═══════════════════════════════════════════════════════════════════
def fig10_11():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt; import numpy as np
    if (OUT / "timing.png").exists():
        import shutil
        shutil.copy(str(OUT / "timing.png"), str(OUT / "fig10_11_timing.png"))
        print("  fig10_11_timing.png")


# ═══════════════════════════════════════════════════════════════════
#  Fig.13: Ablation — NAC with always_move / always_stay / baseline
# ═══════════════════════════════════════════════════════════════════
def fig13():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt; import numpy as np

    print("  Running NAC ablation (3 strategies x 14 benchmarks)...")
    arch = json.loads((PROJECT / "baselines/neutral-atom-compilation/architecture/default.json").read_text())
    results = {}
    for strat in ["baseline", "always_move", "always_stay"]:
        results[strat] = {}
        for bm in TQE:
            print(f"    {bm} @ {strat}...", end=" ", flush=True)
            r = run_nac(f"tqe/{bm}.qasm", arch, strat)
            results[strat][bm] = {
                "F_total": r["total_fidelity"],
                "F_idle": r["fidelity_idle"],
                "F_tr": r["fidelity_handover"],
                "F_dec": r["fidelity_decoherence"],
                "dur": r["total_duration"],
            }
            print(f"F={r['total_fidelity']:.4f}")

    # Save results
    with open(str(OUT / "fig13_ablation_results.json"), "w") as f:
        json.dump({s: {bm: {k: round(v, 6) if isinstance(v, float) else v for k, v in r.items()}
                       for bm, r in results[s].items()} for s in results}, f, indent=2)

    # Chart
    labels = [b.replace("_n", "\n") for b in TQE]
    x = np.arange(len(TQE)); w = 0.22

    fig, ax = plt.subplots(figsize=(18, 8))
    colors = {"baseline": "#2ca02c", "always_move": "#ff7f0e", "always_stay": "#d62728"}
    for ci, (strat, color) in enumerate(colors.items()):
        vals = [results[strat][bm]["F_total"] for bm in TQE]
        ax.bar(x + (ci - 1) * w, vals, w, label=strat, color=color, alpha=0.85,
               edgecolor="white", linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("F_total", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(fontsize=10)
    ax.set_title("Fig.13: Ablation Study — NAC Routing Strategies (14 benchmarks)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(OUT / "fig13_ablation.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  fig13_ablation.png")


# ═══════════════════════════════════════════════════════════════════
#  Fig.14: Sensitivity heatmap — NAC: f_tr × f_xtalk
# ═══════════════════════════════════════════════════════════════════
def fig14():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt; import numpy as np

    print("  Running NAC sensitivity sweep (f_tr x f_xtalk)...")
    from copy import deepcopy
    arch = json.loads((PROJECT / "baselines/neutral-atom-compilation/architecture/default.json").read_text())

    f_tr_vals = [0.98, 0.99, 0.995, 0.998, 0.999, 0.9995, 0.9999]
    f_xtalk_vals = [0.99, 0.995, 0.9975, 0.999, 0.9995, 0.9998, 0.9999]

    bm = "qft_n10"  # representative benchmark
    err_matrix = np.zeros((len(f_tr_vals), len(f_xtalk_vals)))
    fid_matrix = np.zeros((len(f_tr_vals), len(f_xtalk_vals)))

    for i, ftr in enumerate(f_tr_vals):
        for j, fxtalk in enumerate(f_xtalk_vals):
            a = deepcopy(arch)
            a["operation_fidelity"]["atom_transfer"] = ftr
            a["operation_fidelity"]["two_qubit_gate_for_idle"] = fxtalk
            print(f"    f_tr={ftr} f_xtalk={fxtalk}...", end=" ", flush=True)
            r_base = run_nac(f"tqe/{bm}.qasm", a, "baseline")
            r_am = run_nac(f"tqe/{bm}.qasm", a, "always_move")
            err = r_am["total_fidelity"] - r_base["total_fidelity"]
            err_matrix[i][j] = err
            fid_matrix[i][j] = r_base["total_fidelity"]
            print(f"F={r_base['total_fidelity']:.4f} err={err:+.4f}")

    # Save
    np.savez(str(OUT / "fig14_sensitivity.npz"), err=err_matrix, fid=fid_matrix,
             f_tr=f_tr_vals, f_xtalk=f_xtalk_vals)

    # Heatmap
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(err_matrix, cmap="RdYlGn", aspect="auto", origin="lower",
                    vmin=-0.1, vmax=0.1)
    ax.set_xticks(range(len(f_xtalk_vals)))
    ax.set_xticklabels(f_xtalk_vals, fontsize=8, rotation=45)
    ax.set_yticks(range(len(f_tr_vals)))
    ax.set_yticklabels(f_tr_vals, fontsize=8)
    ax.set_xlabel("f_xtalk (crosstalk fidelity)", fontsize=11)
    ax.set_ylabel("f_tr (transfer fidelity)", fontsize=11)
    ax.set_title(f"Fig.14: NAC Sensitivity — Dynamic vs Always Move ERR ({bm})", fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, label="ERR = AlwaysMove - Baseline")
    # Annotate cells
    for i in range(len(f_tr_vals)):
        for j in range(len(f_xtalk_vals)):
            ax.text(j, i, f"{err_matrix[i][j]:+.3f}", ha="center", va="center", fontsize=7)
    # Mark default parameter point (f_tr=0.999, f_xtalk=0.9975)
    default_i = list(f_tr_vals).index(0.999) if 0.999 in f_tr_vals else None
    default_j = list(f_xtalk_vals).index(0.9975) if 0.9975 in f_xtalk_vals else None
    if default_i is not None and default_j is not None:
        ax.scatter(default_j, default_i, marker='*', s=200, color='black',
                   edgecolors='white', linewidth=1.5, zorder=10)
    fig.tight_layout()
    fig.savefig(str(OUT / "fig14_sensitivity.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  fig14_sensitivity.png")


# ═══════════════════════════════════════════════════════════════════
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("  ZAP vs NAC — Fig.7-14")
    print("=" * 60)

    print("\n[Fig.7] Fidelity breakdown...")
    fig7()

    print("\n[Fig.9] Compiler-dependent losses...")
    fig9()

    print("\n[Fig.10+11] Timing...")
    fig10_11()

    print("\n[Fig.13] Ablation study...")
    fig13()

    print("\n[Fig.14] Sensitivity heatmap...")
    fig14()

    print(f"\n  Done. All figures: {OUT}/")


if __name__ == "__main__":
    main()
