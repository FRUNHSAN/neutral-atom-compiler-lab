"""
reproduce_zap.py — ZAP 原始 benchmark 复现脚本。

在本地环境运行 ZAP 的 TQE benchmark 套件，记录 fidelity 结果，
与 ZAP 论文 Fig.7 对比。这是申请材料图 5 的数据来源。

用法:
  python experiments/reproduce_zap.py                    ← 跑全部 benchmark
  python experiments/reproduce_zap.py --quick             ← 只跑 5 个代表性 benchmark
  python experiments/reproduce_zap.py --benchmark qft_n10 ← 跑单个
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

# Point to ZAP source
ZAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "baselines", "neutral-atom-compilation",
)
sys.path.insert(0, ZAP_PATH)

from zap.zap import Zap

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Benchmark list ──────────────────────────────────────
# From ZAP paper TQE benchmark suite
BENCHMARKS = [
    # 算术/变换
    ("qft_n10",       "tqe/qft_n10.qasm",        10),
    ("adder_n4",      "tqe/adder_n4.qasm",        4),
    ("multiplier_n15","tqe/multiplier_n15.qasm",  15),
    # 优化/模拟
    ("qaoa_n6",       "tqe/qaoa_n6.qasm",         6),
    ("ising_n26",     "tqe/ising_n26.qasm",      26),
    # 数据/ML
    ("qram_n20",      "tqe/qram_n20.qasm",       20),
    ("knn_n25",       "tqe/knn_n25.qasm",        25),
    ("vqc_n15",       "tqe/vqc_n15.qasm",        15),
    # 态制备
    ("ghz_n30",       "tqe/ghz_n30.qasm",        30),
    ("wstate_n27",    "tqe/wstate_n27.qasm",      27),
    ("cat_n35",       "tqe/cat_n35.qasm",        35),
    # 其他
    ("bv_n14",        "tqe/bv_n14.qasm",         14),
    ("cc_n12",        "tqe/cc_n12.qasm",         12),
    ("qnn_n15",       "tqe/qnn_n15.qasm",        15),
    ("sat_n11",       "tqe/sat_n11.qasm",        11),
    ("shor_n5",       "tqe/shor_n5.qasm",         5),
]

QUICK = ["qft_n10", "ising_n26", "ghz_n30", "qram_n20", "multiplier_n15"]


def run_one(benchmark_name: str, benchmark_path: str) -> dict | None:
    """Run ZAP on a single benchmark. Returns fidelity dict or None."""
    arch_path = os.path.join(ZAP_PATH, "architecture", "default.json")
    with open(arch_path) as f:
        architecture = json.load(f)

    # Ensure routing config matches ZAP defaults
    architecture.setdefault("routing", {}).setdefault("parallel_priority_weight", 1000.0)

    cwd = os.getcwd()
    try:
        os.chdir(ZAP_PATH)
        zap = Zap(
            benchmark=benchmark_path,
            architecture=architecture,
            initial_mapping=[],
            output_dir=f"reproduce_{benchmark_name}",
            scheduling_strategy="asap_separate",
            placement_strategy="baseline",
            routing_strategy="lookahead",
        )
        zap.solve(simulation=True, animation=False)

        # Read fidelity log
        log_dir = f"results/reproduce_{benchmark_name}/log/"
        if not os.path.exists(log_dir):
            return None
        logs = sorted(
            [f for f in os.listdir(log_dir) if f.endswith(".json")],
            key=lambda x: os.path.getmtime(log_dir + x),
        )
        if logs:
            with open(log_dir + logs[-1]) as f:
                data = json.load(f)
            return data[-1] if isinstance(data, list) else data
        return None
    except Exception as e:
        print(f"    ERROR: {e}")
        return None
    finally:
        os.chdir(cwd)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ZAP benchmark reproduction")
    parser.add_argument("--quick", action="store_true", help="Run only 5 representative benchmarks")
    parser.add_argument("--benchmark", type=str, help="Run a single benchmark by name")
    args = parser.parse_args()

    print("=" * 72)
    print("  ZAP Benchmark Reproduction — Fidelity vs Paper Fig.7")
    print(f"  ZAP path: {ZAP_PATH}")
    print("=" * 72)

    if args.benchmark:
        targets = [(b[0], b[1], b[2]) for b in BENCHMARKS if b[0] == args.benchmark]
        if not targets:
            print(f"  Unknown benchmark: {args.benchmark}")
            print(f"  Available: {', '.join(b[0] for b in BENCHMARKS)}")
            return
    elif args.quick:
        targets = [(b[0], b[1], b[2]) for b in BENCHMARKS if b[0] in QUICK]
        print(f"  Quick mode: {len(targets)} benchmarks")
    else:
        targets = [(b[0], b[1], b[2]) for b in BENCHMARKS]
        print(f"  Full mode: {len(targets)} benchmarks")

    results = {}
    print(f"\n  {'Benchmark':<16s} {'n_q':>5s} {'Fidelity':>12s} {'Time':>8s}  Status")
    print(f"  {'─'*16} {'─'*5} {'─'*12} {'─'*8}  {'─'*6}")

    for name, path, n_q in targets:
        print(f"  {name:<16s} {n_q:>5d} ", end="", flush=True)
        t0 = time.perf_counter()
        entry = run_one(name, path)
        elapsed = time.perf_counter() - t0

        if entry and "total_fidelity" in entry:
            fid = entry["total_fidelity"]
            results[name] = {"fidelity": fid, "n_qubits": n_q, "time_s": elapsed}
            # Extract channel breakdown if available
            for key in ["cir_fidelity_1q_gate", "cir_fidelity_2q_gate",
                         "cir_fidelity_2q_gate_for_idle", "cir_fidelity_atom_transfer",
                         "cir_fidelity_coherence"]:
                if key in entry:
                    results[name][key] = entry[key]
            print(f"{fid:>12.6f} {elapsed:>7.1f}s  OK")
        else:
            print(f"{'N/A':>12s} {elapsed:>7.1f}s  FAIL")
            results[name] = {"fidelity": None, "n_qubits": n_q, "time_s": elapsed, "error": True}

    # Save results
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "zap_reproduction.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}")

    # Summary
    succeeded = sum(1 for r in results.values() if r.get("fidelity") is not None)
    print(f"  {succeeded}/{len(results)} benchmarks completed")


if __name__ == "__main__":
    main()
