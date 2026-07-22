"""AOD router — zone-transfer movement with AOD physics + collision parking.

Enforces three physical constraints at implementation level:
  1. C-qc-aod-routing: atoms in same row/column move with same direction sign
  2. C-qc-parking: path-blocked atoms sidestep (park) before main move
  3. C-qc-crosstalk: only idle atoms IN entanglement zone count as crosstalk
"""

import math
from copy import deepcopy

from .placer import Placer


class Router:
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
        self.architecture = arch
        op_dur = arch.get("operation_duration", {})
        routing_cfg = arch.get("routing", {})

        self.time_atom_transfer = op_dur.get("atom_transfer", 15)
        self.time_2q = op_dur.get("2qGate", 0.25)
        self.time_1q = op_dur.get("1qGate", 0.5)
        self.PARKING_DIST = routing_cfg.get("parking_dist", 1)

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

    # ═══ instruction emitters ═══════════════════════════════════════

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
        for q in qs:
            self.current_mapping[q] = end_locs[q]

    def _move_time(self, d: float) -> float:
        if d <= 0:
            return 0.0
        coeff = float(self.architecture.get("movement", {}).get(
            "time_coefficient", 200.0))
        ref = float(self.architecture.get("movement", {}).get(
            "reference_distance", 110.0))
        return coeff * ((d / ref) ** 0.5)

    # ═══ AOD physics ═══════════════════════════════════════════════
    # Constraint C-qc-aod-routing: same-row → same dx sign; same-col → same dy sign

    @staticmethod
    def _compatible(a, b):
        """Two move vectors (sx,tx,sy,ty) are AOD-compatible."""
        if a[0] == b[0] and a[1] != b[1]: return False  # same row, diff dx sign
        if a[1] == b[1] and a[0] != b[0]: return False  # same col, diff dy sign
        if a[0] < b[0] and a[1] >= b[1]: return False   # crossing row
        if a[0] > b[0] and a[1] <= b[1]: return False
        if a[2] == b[2] and a[3] != b[3]: return False  # same col in y
        if a[3] == b[3] and a[2] != b[2]: return False
        if a[2] < b[2] and a[3] >= b[3]: return False   # crossing col
        if a[2] > b[2] and a[3] <= b[3]: return False
        return True

    def _max_independent_set(self, vectors):
        """Greedy MIS on conflict graph of AOD move vectors."""
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

    # ═══ path verification + parking ════════════════════════════════
    # Constraint C-qc-parking: atom trajectories cannot overlap

    def _verify_path(self, start, end):
        """Check if path from start→end crosses any occupied site. Returns (ok, collision_type)."""
        x1, y1 = start; x2, y2 = end
        if x1 == x2:
            for y in range(min(y1, y2) + 1, max(y1, y2)):
                if (x1, y) in self.current_mapping:
                    return False, "Vertical"
        elif y1 == y2:
            for x in range(min(x1, x2) + 1, max(x1, x2)):
                if (x, y1) in self.current_mapping:
                    return False, "Horizontal"
        else:
            dx, dy = x2 - x1, y2 - y1
            g = abs(math.gcd(dx, dy))
            sx, sy = dx // g, dy // g
            x, y = x1 + sx, y1 + sy
            while (x, y) != (x2, y2):
                if (x, y) in self.current_mapping:
                    return False, "Diagonal"
                x += sx; y += sy
        return True, "Clear"

    def _park_qubits(self, aod_qubits: list[int], tmp_begin: list, tmp_end: list):
        """Phase 1: column collision → parking sidestep. Returns (activated, parked)."""
        activated, parked = [], []
        while True:
            cols = set()
            aod_xys = {self.current_mapping[q] for q in aod_qubits}
            for q in aod_qubits:
                x = self.current_mapping[q][0]
                y = self.current_mapping[q][1]
                for other_q in range(self.n_q):
                    if (other_q not in aod_qubits and
                        self.current_mapping[other_q] == (x, y)):
                        cols.add(x)
                        break

            need_park = [q for q in aod_qubits if self.current_mapping[q][0] in cols]
            if not need_park:
                break

            self._emit_activate(need_park)
            activated += need_park
            need_park.sort(key=lambda q: self.current_mapping[q][0])
            offsets = [-len(need_park) // 2 + i for i in range(len(need_park))]
            for i, q in enumerate(need_park):
                tmp_begin[q] = (tmp_begin[q][0] + self.PARKING_DIST * offsets[i],
                                tmp_begin[q][1])
                parked.append(q)
            self._emit_move(need_park, "Park", tmp_begin)
        return activated, parked

    def _resolve_paths(self, aod_qubits: list[int], tmp_begin: list, tmp_end: list,
                        activated: list[int]):
        """Phase 2: path conflict → park further. Returns extended parking list."""
        parked = []
        while True:
            new_park = []
            new_act = []
            for q in aod_qubits:
                ok, ctype = self._verify_path(tmp_begin[q], tmp_end[q])
                if not ok:
                    new_park.append(q)
                    if q not in activated:
                        activated.append(q)
                        new_act.append(q)
                    if ctype == "Vertical":
                        tmp_end[q] = (tmp_begin[q][0] + self.PARKING_DIST,
                                      tmp_begin[q][1])
                    elif ctype == "Horizontal":
                        tmp_end[q] = (tmp_begin[q][0],
                                      tmp_begin[q][1] + self.PARKING_DIST)
                    elif ctype == "Diagonal":
                        tmp_end[q] = (tmp_end[q][0] + self.PARKING_DIST,
                                      tmp_end[q][1])
                    parked.append(q)
            if new_act:
                self._emit_activate(new_act)
            if not new_park:
                break
        return parked

    def _rearrange(self, aod_qubits: list[int], final_mapping: list[tuple]):
        """Full AOD rearrangement with parking resolution."""
        tmp_begin = deepcopy(self.current_mapping)
        tmp_end = deepcopy(final_mapping)

        activated, parked1 = self._park_qubits(aod_qubits, tmp_begin, tmp_end)
        parked2 = self._resolve_paths(aod_qubits, tmp_begin, tmp_end, activated)

        # Activate remaining (not yet activated)
        remaining = [q for q in aod_qubits if q not in activated]
        if remaining:
            self._emit_activate(remaining)

        # Big move
        self._emit_move(aod_qubits, "BigMove", tmp_end)

        # Deactivate non-parked qubits
        all_parked = set(parked1 + parked2)
        not_parked = [q for q in aod_qubits if q not in all_parked]
        self._emit_deactivate(not_parked)

        # Restore parked qubits to final target
        if all_parked:
            parked_list = list(all_parked)
            self._emit_move(parked_list, "Park", final_mapping)
            self._emit_deactivate(parked_list)

    # ═══ main routing ═══════════════════════════════════════════════

    def route(self) -> list[dict]:
        self._emit_init()

        for stage_idx, gates in enumerate(self.list_full_gates):
            final_mapping = self.placer.place(stage_idx)

            # Build move vectors with AOD compatibility
            vectors = []
            aod_qs = []
            for q in range(self.n_q):
                if self.current_mapping[q] != final_mapping[q]:
                    aod_qs.append(q)
                    vectors.append((
                        self.current_mapping[q][0], final_mapping[q][0],
                        self.current_mapping[q][1], final_mapping[q][1],
                    ))

            # Process moves in AOD-compatible batches
            while vectors:
                start_positions = {(v[0], v[2]) for v in vectors}
                safe = [v for v in vectors if (v[1], v[3]) not in start_positions]
                if not safe:
                    safe = [vectors[0]]
                execute = self._max_independent_set(safe)
                execute_qs = [aod_qs[vectors.index(v)] for v in execute]

                self._rearrange(execute_qs, final_mapping)

                aod_qs = [q for q in aod_qs if q not in execute_qs]
                vectors = [v for v in vectors if v not in execute]

            # Emit gates + crosstalk (only idle qubits IN entanglement zone)
            g1q = [q0 for q0, q1 in gates if q0 == q1]
            g2q = [(q0, q1) for q0, q1 in gates if q0 != q1]
            if g1q:
                self._emit_1q(g1q, stage_idx)
            if g2q:
                self._emit_2q(g2q, stage_idx)
                busy = {q for pair in g2q for q in pair}
                edge = min(y for _, y in self.ent_slm_sites)
                idle = [q for q in range(self.n_q)
                        if q not in busy
                        and self.current_mapping[q] in self.ent_slm_sites
                        and self.current_mapping[q][1] >= edge]
                self._emit_crosstalk(idle)

        return self.instructions
