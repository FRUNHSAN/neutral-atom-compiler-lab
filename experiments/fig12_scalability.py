#!/usr/bin/env python3
"""
fig12_scalability.py — ZAP Fig.12 reproduction: compilation time scalability.

Runs ZAP (and ZAC for small N) on Ising, Cat, Adder, QFT benchmarks
from N=10 to N=500, measuring compilation time.

Usage:
    python experiments/fig12_scalability.py              # ZAP all algos, all N
    python experiments/fig12_scalability.py --cached     # generate chart from cached
    python experiments/fig12_scalability.py --with-zac   # also run ZAC (slow!)

Output:
    application/figures/fig12_scalability.png
    application/fig12_scalability.csv
"""

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZAP_ROOT = PROJECT_ROOT / "baselines" / "neutral-atom-compilation"
ZAC_ROOT = PROJECT_ROOT / "baselines" / "ZAC"
sys.path.insert(0, str(ZAP_ROOT))

from zap.zap import Zap

# ── Configuration ────────────────────────────────────────────────
ALGORITHMS = {
    "Ising": {
        "path_fmt": "scalability/ising/ising_n{n}.qasm",
        "ns": [10, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
        "arch_file": "scale_to_500.json",
    },
    "Cat": {
        "path_fmt": "scalability/cat/cat_n{n}.qasm",
        "ns": [10, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
        "arch_file": "scale_to_500.json",
    },
    "Adder": {
        "path_fmt": "scalability/adder/adder_n{n}.qasm",
        "ns": [4, 10, 28, 46, 64, 91, 118, 136, 181, 226, 271, 316, 361, 406, 433, 460, 496],
        "arch_file": "scale_to_500.json",
    },
    "QFT": {
        "path_fmt": "scalability/qft/qft_n{n}.qasm",
        "ns": [10, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
        "arch_file": "scale_to_500.json",
    },
}

ZAC_MAX_N = 100  # ZAC too slow beyond this


@contextlib.contextmanager
def silence():
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old


def load_architecture(arch_file):
    with open(ZAP_ROOT / "architecture" / arch_file) as f:
        return json.load(f)


def run_zap_scalability(algo_name, n, arch):
    """Run ZAP on one scalability benchmark. Returns compilation_time_s."""
    benchmark_path = ALGORITHMS[algo_name]["path_fmt"].format(n=n)
    orig_cwd = os.getcwd()
    try:
        os.chdir(ZAP_ROOT)
        with silence():
            zap = Zap(
                benchmark=benchmark_path, architecture=arch,
                initial_mapping=[], output_dir=f"fig12/{algo_name}_n{n}",
                scheduling_strategy="asap_separate",
                placement_strategy="baseline", routing_strategy="baseline",
            )
            zap.solve(simulation=False, animation=False)  # no sim, just compile time
        comp_time = zap.results_code.get("compilation_time", 0)
    except Exception as e:
        print(f"  ZAP ERROR {algo_name} n={n}: {e}")
        return None
    finally:
        os.chdir(orig_cwd)
    return comp_time


def run_zac_scalability(algo_name, n):
    """Run ZAC on one scalability benchmark. Returns compilation_time_s."""
    from qiskit import QuantumCircuit, transpile

    qasm_path = ZAP_ROOT / "benchmark" / ALGORITHMS[algo_name]["path_fmt"].format(n=n)
    qasm_str = Path(qasm_path).read_text()

    if "OPENQASM 2" in qasm_str:
        circuit = QuantumCircuit.from_qasm_str(qasm_str)
    else:
        from qiskit_qasm3_import import parse as q3parse
        circuit = q3parse(qasm_str)

    while circuit.data and circuit.data[-1].operation.name == "swap":
        circuit.data.pop()

    n_pre = circuit.num_qubits
    n_2q = sum(1 for ins in circuit.data if ins.operation.num_qubits == 2)
    if n_pre <= 24: opt = 3
    elif n_pre <= 64: opt = 2
    elif n_pre <= 128: opt = 1
    else: opt = 0
    cz = transpile(circuit, basis_gates=["cz", "id", "u2", "u1", "u3"],
                   optimization_level=opt, seed_transpiler=0)

    transpiled_dir = ZAC_ROOT / "benchmark" / "fig12"
    transpiled_dir.mkdir(parents=True, exist_ok=True)
    tp_path = transpiled_dir / f"{algo_name}_n{n}_tp.qasm"
    tp_path.write_text(cz.qasm() if hasattr(cz, 'qasm') else __import__('qiskit').qasm2.dumps(cz))

    exp_spec = {
        "qasm_list": [str(tp_path)],
        "zac_setting": [{
            "arch_spec": str(ZAC_ROOT / "hardware_spec" / "full_architecture.json"),
            "dependency": True, "dir": f"result/zac/fig12/{algo_name}_n{n}/",
            "routing_strategy": "maximalis_sort", "trivial_placement": False,
            "dynamic_placement": True, "use_window": True, "window_size": 1000,
            "use_verifier": True,
        }],
        "simulation": False, "animation": False,
    }
    exp_path = ZAC_ROOT / "exp_setting" / f"_fig12_{algo_name}_{n}.json"
    with open(exp_path, "w") as f:
        json.dump(exp_spec, f, indent=2)

    sys.path.insert(0, str(ZAC_ROOT))
    orig_cwd = os.getcwd()
    try:
        os.chdir(ZAC_ROOT)
        t0 = time.time()
        with silence():
            from zac.ds.architecture import Architecture
            from zac.zac import ZAC as ZACCompiler
            spec_path = exp_spec["zac_setting"][0]["arch_spec"]
            with open(spec_path) as f: spec = json.load(f)
            arch = Architecture(spec)
            arch.preprocessing()
            setting = exp_spec["zac_setting"][0].copy()
            setting["name"] = f"{algo_name}_n{n}"
            zac = ZACCompiler()
            zac.parse_setting(setting)
            zac.set_architecture_spec_path(setting["arch_spec"])
            zac.set_architecture(arch)
            zac.set_program(str(tp_path))
            os.makedirs(zac.dir + "code", exist_ok=True)
            os.makedirs(zac.dir + "time", exist_ok=True)
            zac.solve(save_file=True)
        return time.time() - t0
    except Exception as e:
        print(f"  ZAC ERROR {algo_name} n={n}: {e}")
        return None
    finally:
        os.chdir(orig_cwd)
        exp_path.unlink(missing_ok=True)


def run_all(args):
    """Run ZAP on all algorithms, all N. Optionally ZAC too."""
    with_zac = "--with-zac" in args
    cache = {}

    for algo_name, cfg in ALGORITHMS.items():
        arch = load_architecture(cfg["arch_file"])
        cache.setdefault(algo_name, {"zap": {}, "zac": {}})

        for n in cfg["ns"]:
            print(f"  {algo_name} n={n:>3} ZAP...", end=" ", flush=True)
            t = run_zap_scalability(algo_name, n, arch)
            if t is not None:
                cache[algo_name]["zap"][n] = t
                print(f"{t:.4f}s")
            else:
                print("FAIL")

            if with_zac and n <= ZAC_MAX_N:
                print(f"  {algo_name} n={n:>3} ZAC...", end=" ", flush=True)
                t = run_zac_scalability(algo_name, n)
                if t is not None:
                    cache[algo_name]["zac"][n] = t
                    print(f"{t:.3f}s")
                else:
                    print("FAIL")

    return cache


def generate_chart(cache):
    """Generate Fig.12-style 4-panel compilation time vs N chart."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    algo_order = ["Ising", "Cat", "Adder", "QFT"]

    colors = {"zap": "#2ca02c", "zac": "#ff7f0e"}

    for idx, algo in enumerate(algo_order):
        ax = axes[idx // 2][idx % 2]
        data = cache.get(algo, {})

        for compiler in ["zap", "zac"]:
            pts = sorted(data.get(compiler, {}).items())
            if pts:
                ns, times = zip(*pts)
                ax.plot(ns, times, "o-", color=colors[compiler],
                        label=f"{compiler.upper()}", markersize=5, linewidth=1.5)

        ax.set_title(algo, fontsize=13, fontweight="bold")
        ax.set_xlabel("Number of Qubits", fontsize=10)
        ax.set_ylabel("Compilation Time (s)", fontsize=10)
        ax.set_yscale("log")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(fontsize=9)

    fig.suptitle("Fig.12: Compilation Time Scalability (ZAP only)\n"
                 "Ising, Cat, Adder, QFT — up to 500 qubits",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    out = PROJECT_ROOT / "application" / "figures" / "fig12_scalability.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig.12: {out}")


def export_csv(cache):
    """Export scalability data to CSV."""
    path = PROJECT_ROOT / "application" / "fig12_scalability.csv"
    with open(path, "w") as f:
        f.write("algorithm,n_qubits,compiler,compilation_time_s\n")
        for algo, comps in cache.items():
            for comp, pts in comps.items():
                for n, t in sorted(pts.items()):
                    f.write(f"{algo},{n},{comp.upper()},{t:.6f}\n")
    print(f"  CSV: {path}")


def print_summary(cache):
    """Print key scalability numbers."""
    print()
    for algo, comps in cache.items():
        zap_pts = sorted(comps.get("zap", {}).items())
        if zap_pts:
            n_max, t_max = zap_pts[-1]
            n_min, t_min = zap_pts[0]
            print(f"  {algo}: ZAP N={n_min}→{n_max}: {t_min:.4f}s → {t_max:.4f}s "
                  f"(×{t_max/max(t_min,1e-6):.0f})")


def main():
    cached = "--cached" in sys.argv

    cache_path = PROJECT_ROOT / "application" / "fig12_scalability_cache.json"
    if cached and cache_path.exists():
        cache = json.loads(cache_path.read_text())
        print("Loaded cached scalability results.")
    else:
        print("=" * 72)
        print("  ZAP Fig.12: Compilation Time Scalability")
        print("=" * 72)
        cache = run_all(sys.argv)
        # Save cache
        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)

    print_summary(cache)
    generate_chart(cache)
    export_csv(cache)
    print("  Done.")


if __name__ == "__main__":
    main()
