"""AOD router — simple zone-transfer movement planning.

For zoned architectures, routing is predominantly 1D (storage ↔ entanglement).
Full collision resolution with parking is only needed for dense column sharing.
We use a simplified approach: move qubits directly, resolving trivial conflicts.
"""

import math
import time
from copy import deepcopy

from .placer import Placer


class Router:
    """Per-stage placement + simple AOD move planning → instruction list."""

    def __init__(
        self,
        stg_sites: list[tuple[float, float]],
        ent_sites: list[tuple[float, float]],
        n_qubits: int,
        stages: dict[int, dict],
        list_full_gates: list[list[tuple[int, int]]],
        architecture: dict | None = None,
        placement_strategy: str = "baseline",
        routing_strategy: str = "baseline",
    ):
        arch = architecture or {}
        op_dur = arch.get("operation_duration", {})

        self.time_atom_transfer = op_dur.get("atom_transfer", 15)
        self.time_2q = op_dur.get("2qGate", 0.25)
        self.time_1q = op_dur.get("1qGate", 0.5)

        self.stg_slm_sites = stg_sites
        self.ent_slm_sites = ent_sites
        self.n_q = n_qubits
        self.list_full_gates = list_full_gates

        self.placer = Placer(
            self.stg_slm_sites, self.ent_slm_sites, self.n_q,
            stages, list_full_gates, routing_strategy, architecture,
        )
        self.current_mapping = list(self.placer.current_mapping)

        self.instructions: list[dict] = []
        self.total_duration: float = 0.0

    # ── instruction emitters ──────────────────────────────────────────
    def _emit_init(self):
        self.instructions.append({
            "type": "Init",
            "duration": [0] * self.n_q,
            "locs": [{"id": q, "x": self.current_mapping[q][0],
                      "y": self.current_mapping[q][1]} for q in range(self.n_q)],
        })

    def _emit_1q(self, gates: list[int], stage_idx: int):
        locs = [{"id": q, "x": self.current_mapping[q][0],
                 "y": self.current_mapping[q][1]} for q in gates]
        self.instructions.append({
            "type": "1qGate", "stage": stage_idx,
            "duration": [self.time_1q] * len(gates),
            "qs": gates, "gates": gates, "locs": locs,
        })
        self.total_duration += self.time_1q

    def _emit_2q(self, pairs: list[tuple[int, int]], stage_idx: int):
        qs = [q for pair in pairs for q in pair]
        locs = [{"id": q, "x": self.current_mapping[q][0],
                 "y": self.current_mapping[q][1]} for q in qs]
        self.instructions.append({
            "type": "2qGate", "stage": stage_idx,
            "duration": [self.time_2q] * len(qs),
            "qs": qs, "gates": pairs, "locs": locs,
        })
        self.total_duration += self.time_2q

    def _emit_crosstalk(self, idle_qs: list[int]):
        if not idle_qs:
            return
        locs = [{"id": q, "x": self.current_mapping[q][0],
                 "y": self.current_mapping[q][1]} for q in idle_qs]
        self.instructions.append({
            "type": "Crosstalk",
            "qs": idle_qs,
            "duration": [self.time_2q] * len(idle_qs),
            "locs": locs,
        })

    def _emit_activate(self, qs: list[int]):
        if not qs:
            return
        self.instructions.append({
            "type": "Activate", "qs": qs,
            "duration": [self.time_atom_transfer] * len(qs),
            "locs": [{"id": q, "x": self.current_mapping[q][0],
                      "y": self.current_mapping[q][1]} for q in qs],
        })
        self.total_duration += self.time_atom_transfer

    def _emit_deactivate(self, qs: list[int]):
        if not qs:
            return
        self.instructions.append({
            "type": "Deactivate", "qs": qs,
            "duration": [self.time_atom_transfer] * len(qs),
            "locs": [{"id": q, "x": self.current_mapping[q][0],
                      "y": self.current_mapping[q][1]} for q in qs],
        })
        self.total_duration += self.time_atom_transfer

    def _emit_move(self, qs: list[int], move_type: str, end_locs: list[tuple]):
        if not qs:
            return
        dists = [math.dist(self.current_mapping[q], end_locs[q]) for q in qs]
        durs = [self._move_time(d) for d in dists]
        self.instructions.append({
            "type": move_type, "qs": qs,
            "distance": dists, "duration": durs,
            "locs": [{"id": q, "x_begin": self.current_mapping[q][0],
                      "y_begin": self.current_mapping[q][1],
                      "x_end": end_locs[q][0], "y_end": end_locs[q][1],
                      "movement": dists[i]} for i, q in enumerate(qs)],
        })
        self.total_duration += max(durs) if durs else 0
        for i, q in enumerate(qs):
            self.current_mapping[q] = end_locs[i]

    @staticmethod
    def _move_time(d: float) -> float:
        if d <= 0:
            return 0.0
        return 200.0 * ((d / 110.0) ** 0.5)

    @staticmethod
    def _compatible(a, b):
        """Two 2D move vectors are compatible (can execute in parallel)."""
        if a[0] == b[0] and a[1] != b[1]: return False
        if a[1] == b[1] and a[0] != b[0]: return False
        if a[0] < b[0] and a[1] >= b[1]: return False
        if a[0] > b[0] and a[1] <= b[1]: return False
        if a[2] == b[2] and a[3] != b[3]: return False
        if a[3] == b[3] and a[2] != b[2]: return False
        if a[2] < b[2] and a[3] >= b[3]: return False
        if a[2] > b[2] and a[3] <= b[3]: return False
        return True

    def _maximal_independent_set(self, vectors):
        """Greedy MIS on conflict graph of move vectors."""
        graph = {i: set() for i in range(len(vectors))}
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                if not self._compatible(vectors[i], vectors[j]):
                    graph[i].add(j)
                    graph[j].add(i)

        order = sorted(graph, key=lambda x: len(graph[x]))
        chosen, visited = [], set()
        for node in order:
            if node not in visited:
                chosen.append(node)
                visited.update(graph[node])
                visited.add(node)
        return [vectors[i] for i in chosen]

    # ── main routing loop ─────────────────────────────────────────────
    def route(self) -> list[dict]:
        """Run placement + simple routing across all stages."""
        self._emit_init()

        in_ent = [False] * self.n_q  # track zone membership

        for stage_idx, gates in enumerate(self.list_full_gates):
            final_mapping = self.placer.place(stage_idx)

            # Find qubits that need to move
            vectors = []
            aod_qs = []
            activates = []
            deactivates = []
            for q in range(self.n_q):
                if self.current_mapping[q] == final_mapping[q]:
                    continue

                src_in_ent = self.current_mapping[q] in self.ent_slm_sites
                dst_in_ent = final_mapping[q] in self.ent_slm_sites

                if not src_in_ent and dst_in_ent:
                    activates.append(q)  # storage → entanglement
                elif src_in_ent and not dst_in_ent:
                    deactivates.append(q)  # entanglement → storage

                aod_qs.append(q)
                vectors.append((
                    self.current_mapping[q][0], final_mapping[q][0],
                    self.current_mapping[q][1], final_mapping[q][1],
                ))

            # Activate/deactivate only at zone boundaries
            self._emit_activate(activates)

            # Process moves in compatible batches
            while vectors:
                start_positions = {(v[0], v[2]) for v in vectors}
                safe = [v for v in vectors if (v[1], v[3]) not in start_positions]
                if not safe:
                    safe = [vectors[0]]
                execute = self._maximal_independent_set(safe)
                execute_qs = [aod_qs[vectors.index(v)] for v in execute]

                self._emit_move(execute_qs, "BigMove", final_mapping)

                aod_qs = [q for q in aod_qs if q not in execute_qs]
                vectors = [v for v in vectors if v not in execute]

            self._emit_deactivate(deactivates)

            # Emit gates for this stage
            g1q = [q0 for q0, q1 in gates if q0 == q1]
            g2q = [(q0, q1) for q0, q1 in gates if q0 != q1]
            if g1q:
                self._emit_1q(g1q, stage_idx)
            if g2q:
                self._emit_2q(g2q, stage_idx)
                # Crosstalk: idle qubits still in entanglement zone
                busy = {q for pair in g2q for q in pair}
                edge = min(y for _, y in self.ent_slm_sites)
                idle = [q for q in range(self.n_q)
                        if q not in busy
                        and self.current_mapping[q][1] >= edge
                        and self.current_mapping[q] in self.ent_slm_sites]
                self._emit_crosstalk(idle)

        return self.instructions
