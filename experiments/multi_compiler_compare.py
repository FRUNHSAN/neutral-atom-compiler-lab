#!/usr/bin/env python3
"""
multi_compiler_compare.py — Unified comparison harness for ZAP, Enola, ZAC, PowerMove.

Runs each compiler on the same TQE benchmarks with the same hardware parameters
(f_2q=0.995, f_tr=0.999, T2=1.5e6) and extracts comparable fidelity breakdowns.

Usage:
    python experiments/multi_compiler_compare.py --compiler zap     # ZAP only
    python experiments/multi_compiler_compare.py --compiler enola  # Enola only
    python experiments/multi_compiler_compare.py --benchmark qft_n10  # single benchmark
    python experiments/multi_compiler_compare.py --all             # all compilers, all benchmarks
    python experiments/multi_compiler_compare.py --all --quick     # first 5 benchmarks only

Paper reference: ZAP Fig.9/10/11 — multi-compiler comparison on TQE benchmarks.
"""

import contextlib
import copy
import io
import json
import os
import sys
import time
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZAP_ROOT = PROJECT_ROOT / "baselines" / "neutral-atom-compilation"
ENOLA_ROOT = PROJECT_ROOT / "baselines" / "Enola"
ZAC_ROOT = PROJECT_ROOT / "baselines" / "ZAC"
PM_ROOT = PROJECT_ROOT / "baselines" / "PowerMove"

# Add to path for imports
sys.path.insert(0, str(ZAP_ROOT))
sys.path.insert(0, str(ENOLA_ROOT))

# ── Standard hardware parameters (paper Table 1) ──────────────────
HW_PARAMS = {
    "f_2q": 0.995,
    "f_1q": 0.9997,
    "f_tr": 0.999,
    "T2": 1_500_000,  # us
    "t_2q": 0.36,
    "t_1q": 52,
    "t_tr": 15,
}

# ── TQE benchmarks ───────────────────────────────────────────────
TQE_BENCHMARKS = [
    "adder_n4", "qaoa_n6", "qft_n10", "sat_n11", "bv_n14",
    "multiplier_n15", "qnn_n15", "vqc_n15", "qram_n20",
    "knn_n25", "ising_n26", "wstate_n27", "ghz_n30", "cat_n35",
]

TQE_QASM_DIR = ZAP_ROOT / "benchmark" / "tqe"


@contextlib.contextmanager
def silence_stdout():
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old


def extract_2q_gates(qasm_path):
    """Extract 2-qubit gate list from a QASM file (2.0 or 3.0),
    transpiled to CZ basis.  Returns (gates_2q, n_qubits).

    Uses the same version-detection logic as ZAP's set_program().
    """
    from qiskit import QuantumCircuit, transpile
    from qiskit_qasm3_import import parse as qasm3_parse

    qasm_str = Path(qasm_path).read_text()

    # ── Version detection (matching ZAP's set_program) ──
    if "OPENQASM 2" in qasm_str:
        circuit = QuantumCircuit.from_qasm_str(qasm_str)
    elif "OPENQASM 3" in qasm_str:
        circuit = qasm3_parse(qasm_str)
    else:
        raise ValueError(f"Unsupported QASM version in {qasm_path}")

    # ── Strip trailing swaps (matching ZAP) ──
    swap_remain = True
    while swap_remain and circuit.data:
        if circuit.data[-1][0].name == "swap":
            circuit.data.pop()
        else:
            swap_remain = False

    # ── Transpile optimization level (matching ZAP) ──
    n_pre = circuit.num_qubits
    n_2q_orig = sum(1 for ins in circuit.data if ins.operation.num_qubits == 2)
    if n_pre <= 24:
        opt_level = 3
    elif n_pre <= 64:
        opt_level = 2
    elif n_pre <= 128:
        opt_level = 1
    else:
        opt_level = 0

    cz = transpile(circuit, basis_gates=["cz", "id", "u2", "u1", "u3"],
                   optimization_level=opt_level, seed_transpiler=0)

    gates_2q = []
    for ins in cz.data:
        if ins.operation.num_qubits == 2:
            gates_2q.append((ins.qubits[0]._index, ins.qubits[1]._index))
    return gates_2q, cz.num_qubits


# ═══════════════════════════════════════════════════════════════════
#  ZAP ADAPTER
# ═══════════════════════════════════════════════════════════════════

def run_zap(benchmark_name):
    """Run ZAP on a TQE benchmark. Returns fidelity dict."""
    from zap.zap import Zap

    benchmark_path = f"tqe/{benchmark_name}.qasm"
    with open(ZAP_ROOT / "architecture" / "default.json") as f:
        arch = json.load(f)

    orig_cwd = os.getcwd()
    try:
        os.chdir(ZAP_ROOT)
        t0 = time.time()
        with silence_stdout():
            zap = Zap(benchmark=benchmark_path, architecture=arch,
                      initial_mapping=[], output_dir=f"compare/zap/{benchmark_name}",
                      scheduling_strategy="asap_separate",
                      placement_strategy="baseline", routing_strategy="baseline")
            zap.solve(simulation=True, animation=False)
        elapsed = time.time() - t0
    finally:
        os.chdir(orig_cwd)

    log_dir = ZAP_ROOT / "results" / "compare" / "zap" / benchmark_name / "log"
    jf = sorted(log_dir.glob("*.json"))
    if not jf:
        return None
    rec = json.loads(jf[-1].read_text())
    rec = rec[-1] if isinstance(rec, list) else rec

    return {
        "compiler": "ZAP",
        "benchmark": benchmark_name,
        "compilation_time_s": rec.get("compilation_time", elapsed),
        "f_total": rec["total_fidelity"],
        "f_2q": rec["fidelity_2q_gate"],
        "f_idle": rec["fidelity_idle"],
        "f_tr": rec["fidelity_handover"],
        "f_dec": rec["fidelity_decoherence"],
        "f_1q": rec["fidelity_1q_gate"],
        "total_duration_us": rec["total_duration"],
        "n_2q": rec["n_2q_gate"],
        "n_1q": rec["n_1q_gate"],
        "stages": rec["stage"],
    }


# ═══════════════════════════════════════════════════════════════════
#  ENOLA ADAPTER
# ═══════════════════════════════════════════════════════════════════

def run_enola(benchmark_name):
    """Run Enola on a TQE benchmark. Returns fidelity dict.

    Enola only processes 2-qubit gates. We extract them from the
    transpiled QASM and feed them to Enola's API.
    Enola is SLOW (~60s for small benchmarks due to SA placement).
    """
    qasm_path = TQE_QASM_DIR / f"{benchmark_name}.qasm"
    gates_2q, n_qubits = extract_2q_gates(qasm_path)

    # Enola expects a simple 2q gate list
    arch_dim = max(16, int(n_qubits * 1.5))  # ensure enough capacity

    from enola.enola import Enola

    # Enola's Simulator uses same default params as ZAP
    # f_2q=0.995, f_1q=0.9997, f_tr=0.999, T2=1.5e6
    t0 = time.time()
    with silence_stdout():
        enola = Enola(
            benchmark_name,
            dir="./results/compare/enola/",
            trivial_layout=False,
            routing_strategy="maximalis",
            reverse_to_initial=False,
            dependency=True,
            use_window=False,
            full_code=False,
        )
        enola.setArchitecture([arch_dim, arch_dim, arch_dim, arch_dim])
        enola.setProgram(gates_2q)
        enola.solve(save_file=True)
    compilation_time = time.time() - t0

    # Run Enola's simulator on the output
    from simulator import Simulator
    code_file = ENOLA_ROOT / "results" / "compare" / "enola" / f"{benchmark_name}_code.json"
    if not code_file.exists():
        return None

    # Enola's Simulator defaults match ZAP: f_2q=0.995, f_tr=0.999, T2=1.5e6
    sim = Simulator(str(code_file), {})
    result = sim.simulate()

    # Parse Enola output to match ZAP's keys
    # Enola: cir_fidelity, cir_fidelity_2q_gate, cir_fidelity_2q_gate_for_idle,
    #        cir_fidelity_atom_transfer, cir_fidelity_coherence, cir_fidelity_1q_gate
    # ZAP:   total_fidelity, fidelity_2q_gate, fidelity_idle,
    #        fidelity_handover, fidelity_decoherence, fidelity_1q_gate

    return {
        "compiler": "Enola",
        "benchmark": benchmark_name,
        "compilation_time_s": compilation_time,
        "f_total": result["cir_fidelity"],
        "f_2q": result["cir_fidelity_2q_gate"],
        "f_idle": result["cir_fidelity_2q_gate_for_idle"],
        "f_tr": result["cir_fidelity_atom_transfer"],
        "f_dec": result["cir_fidelity_coherence"],
        "f_1q": result.get("cir_fidelity_1q_gate", 1.0),
        "total_duration_us": result.get("cir_duration", 0),
        "n_2q": len(gates_2q),
        "n_1q": 0,  # Enola doesn't schedule 1q gates
        "stages": result.get("num_movement_stage", 0),
        "movement_time_ratio": result.get("movement_time_ratio", [])[:3],
    }


# ═══════════════════════════════════════════════════════════════════
#  ZAC ADAPTER
# ═══════════════════════════════════════════════════════════════════

def run_zac(benchmark_name):
    """Run ZAC on a TQE benchmark. Returns fidelity dict.

    ZAC expects pre-transpiled QASM files. We transpile the benchmark
    to CZ+U basis and save it, then create an experiment JSON.
    """
    import tempfile

    qasm_path = TQE_QASM_DIR / f"{benchmark_name}.qasm"

    # Use the fixed version-aware parser to get transpiled CZ circuit
    from qiskit import QuantumCircuit, transpile, qasm2

    qasm_str = Path(qasm_path).read_text()
    if "OPENQASM 2" in qasm_str:
        circuit = QuantumCircuit.from_qasm_str(qasm_str)
    elif "OPENQASM 3" in qasm_str:
        from qiskit_qasm3_import import parse as qasm3_parse
        circuit = qasm3_parse(qasm_str)
    else:
        raise ValueError(f"Unsupported QASM version in {qasm_path}")

    # Strip trailing swaps (Qiskit 1.2+ compatible)
    while circuit.data:
        last_op = circuit.data[-1].operation
        if last_op.name == "swap":
            circuit.data.pop()
        else:
            break

    n_pre = circuit.num_qubits
    n_2q_orig = sum(1 for ins in circuit.data if ins.operation.num_qubits == 2)
    if n_pre <= 24:
        opt_level = 3
    elif n_pre <= 64:
        opt_level = 2
    elif n_pre <= 128:
        opt_level = 1
    else:
        opt_level = 0
    cz = transpile(circuit, basis_gates=["cz", "id", "u2", "u1", "u3"],
                   optimization_level=opt_level, seed_transpiler=0)

    # Save transpiled QASM 2.0
    transpiled_dir = ZAC_ROOT / "benchmark" / "tqe_transpiled"
    transpiled_dir.mkdir(parents=True, exist_ok=True)
    transpiled_path = transpiled_dir / f"{benchmark_name}_transpiled.qasm"
    transpiled_path.write_text(qasm2.dumps(cz))

    # Create ZAC experiment JSON
    exp_spec = {
        "qasm_list": [str(transpiled_path)],
        "zac_setting": [{
            "arch_spec": str(ZAC_ROOT / "hardware_spec" / "full_architecture.json"),
            "dependency": True,
            "dir": f"result/zac/compare/{benchmark_name}/",
            "routing_strategy": "maximalis_sort",
            "trivial_placement": False,
            "dynamic_placement": True,
            "use_window": True,
            "window_size": 1000,
            "use_verifier": True,
        }],
        "simulation": True,
        "animation": False,
    }

    exp_path = ZAC_ROOT / "exp_setting" / f"_compare_{benchmark_name}.json"
    with open(exp_path, "w") as f:
        json.dump(exp_spec, f, indent=2)

    # Run ZAC
    sys.path.insert(0, str(ZAC_ROOT))
    orig_cwd = os.getcwd()
    try:
        os.chdir(ZAC_ROOT)
        t0 = time.time()
        with silence_stdout():
            # Import and run ZAC inline (avoids subprocess)
            from zac.ds.architecture import Architecture
            from zac.zac import ZAC as ZACCompiler
            from zac.simulator.simulator import Simulator as ZACSimulator

            spec_path = exp_spec["zac_setting"][0]["arch_spec"]
            with open(spec_path) as f:
                spec = json.load(f)
            arch = Architecture(spec)
            arch.preprocessing()

            setting = exp_spec["zac_setting"][0].copy()
            setting["name"] = benchmark_name

            zac = ZACCompiler()
            zac.parse_setting(setting)
            zac.set_architecture_spec_path(setting["arch_spec"])
            zac.set_architecture(arch)
            zac.set_program(str(transpiled_path))

            os.makedirs(zac.dir + "code", exist_ok=True)
            os.makedirs(zac.dir + "time", exist_ok=True)
            zac.solve(save_file=True)

            sim = ZACSimulator()
            sim.set_arch_spec(spec)
            sim.parse(zac.code_filename)
            result = sim.simulate()

        compilation_time = time.time() - t0
    finally:
        os.chdir(orig_cwd)

    # Clean up temp files
    exp_path.unlink(missing_ok=True)

    return {
        "compiler": "ZAC",
        "benchmark": benchmark_name,
        "compilation_time_s": compilation_time,
        "f_total": result["cir_fidelity"],
        "f_2q": result["cir_fidelity_2q_gate"],
        "f_idle": result["cir_fidelity_2q_gate_for_idle"],
        "f_tr": result["cir_fidelity_atom_transfer"],
        "f_dec": result["cir_fidelity_coherence"],
        "f_1q": result.get("cir_fidelity_1q_gate", 1.0),
        "total_duration_us": result.get("cir_duration", 0),
        "n_2q": sum(1 for ins in cz.data if ins.operation.num_qubits == 2),
        "n_1q": sum(1 for ins in cz.data if ins.operation.num_qubits == 1),
        "stages": 0,
    }


# ═══════════════════════════════════════════════════════════════════
#  POWERMOVE ADAPTER
# ═══════════════════════════════════════════════════════════════════

def run_powermove(benchmark_name):
    """Run PowerMove on a TQE benchmark. Returns fidelity dict.

    PowerMove has no CLI — we call mvqc() directly.
    Uses the same hardware parameters as ZAP (f_2q=0.995, f_tr=0.999, T2=1.5e6).
    Note: PowerMove defaults f_1q=0.995 but paper excludes 1q fidelity anyway.
    """
    qasm_path = TQE_QASM_DIR / f"{benchmark_name}.qasm"
    gates_2q, n_qubits = extract_2q_gates(qasm_path)

    # PowerMove needs CZ gate blocks (parallel groups)
    # Use gate_scheduling from PowerMove
    sys.path.insert(0, str(PM_ROOT))
    from scheduler.gate_scheduler import gate_scheduling

    # gate_scheduling returns GATE INDICES, not gate tuples.
    # Convert indices back to (q0, q1) tuples for downstream code.
    cz_blocks_idx = gate_scheduling(n_qubits, gates_2q)
    cz_blocks = [[gates_2q[i] for i in block] for block in cz_blocks_idx]

    # Architecture dimension: PowerMove uses a Row×Row grid
    # plus storage rows below. Match ZAP's capacity (~80 storage).
    Row = max(16, int(n_qubits * 2.0))  # ensure enough AOD rows for complex topologies

    # Override PowerMove's globals to match ZAP's parameters
    import mvqc as pm
    pm.Fidelity_2Q_Gate = HW_PARAMS["f_2q"]
    pm.Fidelity_1Q_Gate = HW_PARAMS["f_1q"]  # was 0.995, paper uses 0.9997
    pm.Fidelity_Atom_Transfer = HW_PARAMS["f_tr"]
    pm.Coherence_Time = HW_PARAMS["T2"]

    t0 = time.time()
    with silence_stdout():
        result = pm.mvqc(cz_blocks, Row, n_qubits, storage_flag=True)
    compilation_time = time.time() - t0

    # result: (transfer_dur, move_dur, cir_fidelity, cir_fidelity_1q_gate,
    #           cir_fidelity_2q_gate, cir_fidelity_2q_gate_for_idle,
    #           cir_fidelity_atom_transfer, cir_fidelity_coherence, num_movement_stage)
    (tr_dur, mv_dur, f_total, f_1q, f_2q, f_idle, f_tr, f_dec, n_mv_stages) = result

    return {
        "compiler": "PowerMove",
        "benchmark": benchmark_name,
        "compilation_time_s": compilation_time,
        "f_total": f_total,
        "f_2q": f_2q,
        "f_idle": f_idle,
        "f_tr": f_tr,
        "f_dec": f_dec,
        "f_1q": f_1q,
        "total_duration_us": tr_dur + mv_dur,
        "n_2q": len(gates_2q),
        "n_1q": 0,
        "stages": n_mv_stages,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

RUNNERS = {
    "zap": run_zap,
    "enola": run_enola,
    "zac": run_zac,
    "powermove": run_powermove,
}


def print_table(results):
    """Print comparison table."""
    if not results:
        return
    print()
    header = (f"{'Benchmark':<18} {'Compiler':<12} "
              f"{'F_total':>10} {'F_2q':>10} {'F_idle':>10} "
              f"{'F_tr':>10} {'F_dec':>10} {'Compile(s)':>10}")
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: (x["benchmark"], x["compiler"])):
        print(f"{r['benchmark']:<18} {r['compiler']:<12} "
              f"{r['f_total']:>10.4f} {r['f_2q']:>10.4f} {r['f_idle']:>10.4f} "
              f"{r['f_tr']:>10.4f} {r['f_dec']:>10.4f} "
              f"{r['compilation_time_s']:>10.3f}")
    print("-" * len(header))
    print(f"  {len(results)} results")
    print()


def save_results(results, path):
    """Save all results to JSON, merging with existing entries."""
    existing = []
    if os.path.exists(path):
        try:
            existing = json.loads(Path(path).read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Update: replace entries with same compiler+benchmark, add new ones
    keyed = {(r.get("compiler",""), r.get("benchmark","")): r for r in existing}
    for r in results:
        keyed[(r.get("compiler",""), r.get("benchmark",""))] = r

    merged = sorted(keyed.values(), key=lambda x: (x.get("benchmark",""), x.get("compiler","")))
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"  Saved: {path} ({len(merged)} entries)")


def main():
    compiler_filter = None
    benchmark_filter = None
    use_all = "--all" in sys.argv
    use_quick = "--quick" in sys.argv

    for arg in sys.argv:
        if arg.startswith("--compiler="):
            compiler_filter = arg.split("=", 1)[1]
        if arg.startswith("--benchmark="):
            benchmark_filter = arg.split("=", 1)[1]

    if use_all:
        compilers = list(RUNNERS.keys())
    elif compiler_filter:
        compilers = [c for c in compiler_filter.split(",") if c in RUNNERS]
    else:
        compilers = ["zap"]

    benchmarks = [benchmark_filter] if benchmark_filter else TQE_BENCHMARKS
    if use_quick:
        benchmarks = benchmarks[:5]

    print("=" * 72)
    print("  Multi-Compiler Comparison")
    print(f"  Compilers:  {compilers}")
    print(f"  Benchmarks: {len(benchmarks)}")
    print(f"  HW params:  f_2q={HW_PARAMS['f_2q']}, f_tr={HW_PARAMS['f_tr']}, "
          f"T2={HW_PARAMS['T2']/1e6:.1f}s")
    print("=" * 72)

    results = []
    n_total = len(benchmarks) * len(compilers)
    n_done = 0
    t_start = time.time()

    for bm in benchmarks:
        for compiler_name in compilers:
            n_done += 1
            label = f"{bm} @ {compiler_name}"
            print(f"  [{n_done}/{n_total}] {label}...", end=" ", flush=True)

            try:
                t0 = time.time()
                rec = RUNNERS[compiler_name](bm)
                elapsed = time.time() - t0
                if rec:
                    results.append(rec)
                    print(f"F={rec['f_total']:.4f} ({elapsed:.1f}s)")
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")

    total_elapsed = time.time() - t_start
    print(f"\n  Total: {n_total} runs in {total_elapsed:.1f}s, "
          f"{len(results)} successful")

    print_table(results)

    out_path = PROJECT_ROOT / "application" / "multi_compiler_results.json"
    save_results(results, out_path)


if __name__ == "__main__":
    main()
