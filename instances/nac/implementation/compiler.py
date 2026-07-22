"""NAC — Neutral Atom Compiler.

Constraint-engineered compiler for zoned neutral-atom architectures.
Reads hardware boundary, bridges, and benchmark; produces compiled instructions
and fidelity decomposition.

API is compatible with ZAP's Zap class for drop-in comparison.
"""

import json
import os
import time
from pathlib import Path

import yaml as _yaml

from qiskit import transpile, QuantumCircuit
from qiskit_qasm3_import import parse as qasm3_parse

from .scheduler import Scheduler
from .placer import movement_duration_um
from .router import Router
from .simulator import Simulator


class Compiler:
    """Compile a QASM benchmark onto a zoned neutral-atom architecture."""

    def __init__(
        self,
        benchmark: str,
        architecture: dict | None = None,
        initial_mapping: list | None = None,
        output_dir: str = "",
        scheduling_strategy: str = "asap_separate",
        placement_strategy: str = "baseline",
        routing_strategy: str = "baseline",
    ):
        self.benchmark = benchmark
        self.architecture = architecture or {}
        self.output_dir = output_dir
        self.scheduling_strategy = scheduling_strategy
        self.placement_strategy = placement_strategy
        self.routing_strategy = routing_strategy

        # Parse benchmark path
        p = Path(benchmark.replace("\\", "/"))
        self.benchmark_name = p.stem
        self.benchmark_type = p.suffix.lstrip(".")

        # Parse SLM sites from architecture
        self.stg_sites: list[tuple] = []
        self.ent_sites: list[tuple] = []
        self._parse_sites()

        # Gate list
        self.g_q: list[tuple[int, int]] = []
        self.n_q: int = 0
        self.n_1q: int = 0
        self.n_2q: int = 0

        # Results
        self.results: dict = {}
        self.instructions: list[dict] = []
        self.compilation_time_s: float = 0.0

    def _parse_sites(self):
        for zone in self.architecture.get("storage_zones", []):
            for slm in zone.get("slms", []):
                x0, y0 = slm["location"]
                sx, sy = slm["site_seperation"]
                for j in range(slm["r"]):
                    for i in range(slm["c"]):
                        self.stg_sites.append((x0 + i * sx, y0 + j * sy))
        self.stg_sites = sorted(set(self.stg_sites))

        for zone in self.architecture.get("entanglement_zones", []):
            for slm in zone.get("slms", []):
                x0, y0 = slm["location"]
                sx, sy = slm["site_seperation"]
                for j in range(slm["r"]):
                    for i in range(slm["c"]):
                        self.ent_sites.append((x0 + i * sx, y0 + j * sy))
        self.ent_sites = sorted(set(self.ent_sites))

    def _merge_hardware_defaults(self):
        """Fill architecture dict with boundary + bridge defaults."""
        defaults = {
            "hardware": {
                "rydberg_radius_um": 5.0,
            },
            "movement": {
                "time_coefficient": 200.0,
                "reference_distance": 110.0,
            },
            "routing": {
                "parking_dist": 1,
                "parallel_priority_weight": 1000.0,
                "initial_mapping_parallel_lookahead": 3,
                "idle_cost_alpha": 1.0,
            },
        }
        for section, vals in defaults.items():
            self.architecture.setdefault(section, {}).update(
                {k: v for k, v in vals.items()
                 if k not in self.architecture.get(section, {})}
            )

        # Override routing defaults with BR-keep-vs-move bridge values
        bridge_path = Path(__file__).resolve().parent.parent / "bridges" / "BR-keep-vs-move.yaml"
        if bridge_path.exists():
            try:
                import yaml as _yaml
                bridge = _yaml.safe_load(bridge_path.read_text(encoding="utf-8"))
                resolve = bridge.get("resolve_fn", {})
                alpha = resolve.get("params", {}).get("alpha")
                if alpha is not None:
                    self.architecture["routing"]["idle_cost_alpha"] = float(alpha)
                strategies = resolve.get("params", {}).get("strategies", {})
                if strategies and self.routing_strategy not in strategies:
                    default = resolve.get("default_strategy", "baseline")
                    print(f"  [NAC] routing_strategy={self.routing_strategy!r} "
                          f"not in bridge strategies {list(strategies)}, "
                          f"falling back to {default!r}")
                    self.routing_strategy = default
            except Exception:
                pass  # bridge YAML is advisory; architecture defaults suffice

    def _load_benchmark(self, benchmark_dir: str = "benchmark"):
        """Load QASM, transpile to CZ basis, extract flat gate list."""
        bench_path = Path(benchmark_dir) / self.benchmark
        qasm_str = bench_path.read_text()

        if "OPENQASM 2" in qasm_str:
            circuit = QuantumCircuit.from_qasm_str(qasm_str)
        elif "OPENQASM 3" in qasm_str:
            circuit = qasm3_parse(qasm_str)
        else:
            raise ValueError(f"Unsupported QASM format in {bench_path}")

        # Strip trailing swaps
        while circuit.data and circuit.data[-1].operation.name == "swap":
            circuit.data.pop()

        n_pre = circuit.num_qubits
        if n_pre <= 24:
            opt = 3
        elif n_pre <= 64:
            opt = 2
        elif n_pre <= 128:
            opt = 1
        else:
            opt = 0

        print(f"  [NAC] transpile {n_pre} qubits → CZ basis (opt_level={opt})…")
        cz = transpile(circuit, basis_gates=["cz", "id", "u2", "u1", "u3"],
                       optimization_level=opt, seed_transpiler=0)
        print(f"  [NAC] transpile done: {cz.num_qubits} qubits, "
              f"{len(cz.data)} ops")

        self.n_q = cz.num_qubits
        self.g_q = []
        self.n_2q = 0
        self.n_1q = 0
        for ins in cz.data:
            if ins.operation.num_qubits == 2:
                self.n_2q += 1
                self.g_q.append((ins.qubits[0]._index, ins.qubits[1]._index))
            elif ins.operation.name not in ("measure", "barrier"):
                self.n_1q += 1
                self.g_q.append((ins.qubits[0]._index, ins.qubits[0]._index))

        n_stg = len(self.stg_sites)
        if self.n_q > n_stg:
            raise ValueError(
                f"Circuit needs {self.n_q} qubits but architecture has "
                f"only {n_stg} storage traps. Use scale_to_500.json."
            )

    def solve(self, simulation: bool = True, benchmark_dir: str = "benchmark"):
        """Main compile pipeline: schedule → place+route → simulate."""
        t0 = time.time()

        self._load_benchmark(benchmark_dir)
        print(f"  [NAC] {self.n_q} qubits, {self.n_2q} CZ gates, "
              f"{self.n_1q} 1q gates")

        # Stage 1: schedule
        print(f"  [NAC] scheduling ({self.scheduling_strategy})…")
        scheduler = Scheduler(self.g_q, self.n_q, self.scheduling_strategy)
        list_gates = scheduler.as_gate_list()
        print(f"  [NAC] {scheduler.num_stages} stages")

        # Merge hardware defaults from boundary into architecture dict
        self._merge_hardware_defaults()

        # Stage 2: place + route
        print(f"  [NAC] placing+routing ({self.routing_strategy})…")
        router = Router(
            self.stg_sites, self.ent_sites, self.n_q,
            scheduler.stages, list_gates,
            self.architecture, self.placement_strategy, self.routing_strategy,
        )
        self.instructions = router.route()
        self.compilation_time_s = time.time() - t0

        print(f"  [NAC] {len(self.instructions)} instructions, "
              f"compile={self.compilation_time_s:.3f}s")

        # Stage 3: simulate
        sim = None
        if simulation:
            print(f"  [NAC] simulating…")
            sim = Simulator(self.instructions, self.n_q, self.n_1q, self.n_2q,
                            self.architecture)
            self.results = sim.as_dict()
            self.results["compilation_time"] = round(self.compilation_time_s, 4)
            self.results["n_q"] = self.n_q
            self.results["stage_count"] = scheduler.num_stages
            self._log(sim)

        print(f"  [NAC] done.\n")
        return sim

    def _log(self, sim: Simulator):
        """Append result to results/<output_dir>/log/<benchmark>.json."""
        if not self.output_dir:
            return
        log_dir = Path("results") / self.output_dir / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{self.benchmark_name}.json"

        entry = {
            "algorithm": self.benchmark_name,
            "n_qubits": self.n_q,
            "n_1q_gate": self.n_1q,
            "n_2q_gate": self.n_2q,
            "total_duration": round(sim.total_duration, 6),
            "compilation_time": round(self.compilation_time_s, 4),
            "total_fidelity": round(sim.fidelity_total, 8),
            "fidelity_1q_gate": round(sim.fidelity_1q, 8),
            "fidelity_2q_gate": round(sim.fidelity_2q, 8),
            "fidelity_idle": round(sim.fidelity_idle, 8),
            "fidelity_handover": round(sim.fidelity_tr, 8),
            "fidelity_decoherence": round(sim.fidelity_dec, 8),
        }

        existing = []
        if log_path.exists():
            existing = json.loads(log_path.read_text())
        existing.append(entry)
        log_path.write_text(json.dumps(existing, indent=2))
