"""Qubit placer — site assignment and per-stage Eq.15 stay-or-move decision.

Reads B-nac-hardware (site geometry, timing, fidelity params),
BR-keep-vs-move (idle strategy), BR-qubit-priority (qubit weighting),
BR-parallel-vs-distance (parallelism weight).
"""

import math
import numpy as np

R_BLOCKADE = 5  # um, Rydberg interaction radius

# ── movement duration (shared heuristic with router) ──────────────────
def movement_duration_um(d: float) -> float:
    if d <= 0:
        return 0.0
    return 200.0 * ((d / 110.0) ** 0.5)


class Placer:
    def __init__(
        self,
        stg_sites: list[tuple[float, float]],
        ent_sites: list[tuple[float, float]],
        n_qubits: int,
        stages: dict[int, dict],
        list_full_gates: list[list[tuple[int, int]]],
        routing_strategy: str = "baseline",
        architecture: dict | None = None,
    ):
        self.stg_slm_sites = list(stg_sites)
        self.ent_slm_sites = list(ent_sites)
        self.n_q = n_qubits
        self.stages = stages
        self.list_full_gates = list_full_gates
        self.routing_strategy = routing_strategy

        arch = architecture or {}
        op_fid = arch.get("operation_fidelity", {})
        routing_cfg = arch.get("routing", {})

        f2 = op_fid.get("two_qubit_gate", 0.995)
        self.fidelity_2q_idle = 1.0 - (1.0 - f2) / 2.0
        self.fidelity_atom_transfer = op_fid.get("atom_transfer", 0.999)
        self.time_coherence = arch.get("qubit_spec", {}).get("T2", 1.5e6)
        self.parallel_weight = float(routing_cfg.get("parallel_priority_weight", 1000.0))
        self.lookahead = int(routing_cfg.get("initial_mapping_parallel_lookahead", 3))
        self.alpha = float(routing_cfg.get("idle_cost_alpha", 1.0))

        # Build all valid entanglement pairs (distance < R_BLOCKADE)
        self.all_pairs = [
            (a, b) for i, a in enumerate(self.ent_slm_sites)
            for j, b in enumerate(self.ent_slm_sites)
            if i < j and math.dist(a, b) < R_BLOCKADE
        ]

        # Init mapping
        self.current_mapping: list[tuple[float, float]] = [(-1.0, -1.0)] * self.n_q
        self._init_sites()
        self._init_qubit_mapping()
        self.initial_mapping = list(self.current_mapping)
        self._planned_vectors: list[tuple] = []

    # ── site helpers ──────────────────────────────────────────────────
    def _init_sites(self):
        """Use all available sites — no trimming. Site count is architecture-defined."""
        # Keep all sites. ZAP doesn't trim. Trimming causes qubits to run out
        # of storage capacity on dense circuits. The architecture JSON defines
        # the site budget; the placer should use all of it.
        pass

    def _init_qubit_mapping(self):
        """Weighted assignment: high-gate-count qubits → closest storage sites."""
        # Qubit gate-participation weights
        weights = np.zeros(self.n_q)
        for s, gates in enumerate(self.list_full_gates):
            w = 1.0 / (s + 1)
            for q0, q1 in gates:
                if q0 != q1:
                    weights[q0] += w
                    weights[q1] += w

        qubit_order = sorted(range(self.n_q), key=lambda i: weights[i], reverse=True)

        # Nearest entanglement site per storage site
        nearest_ent = {}
        nearest_dist = {}
        for site in self.stg_slm_sites:
            best = min(self.ent_slm_sites, key=lambda ez: math.dist(site, ez))
            nearest_ent[site] = best
            nearest_dist[site] = math.dist(site, best)

        # First 2q stage per qubit
        first_2q = [None] * self.n_q
        for si, gates in enumerate(self.list_full_gates):
            for q0, q1 in gates:
                if q0 != q1:
                    if first_2q[q0] is None:
                        first_2q[q0] = si
                    if first_2q[q1] is None:
                        first_2q[q1] = si

        assigned: list[tuple] = []
        planned: list[tuple] = []

        for q in qubit_order:
            available = [s for s in self.stg_slm_sites if s not in assigned]
            if not available:
                break

            best_site = None
            best_rank = None
            for site in available:
                vector = None
                stage_idx = first_2q[q]
                if stage_idx is not None and stage_idx <= self.lookahead:
                    target = nearest_ent[site]
                    vector = (site[0], target[0], site[1], target[1])

                conflicts = 0
                if vector is not None:
                    conflicts = sum(1 for p in planned if not self._compatible(vector, p))

                score = self.parallel_weight * conflicts + nearest_dist[site]
                rank = (score, conflicts, nearest_dist[site])
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_site = site

            self.current_mapping[q] = best_site
            assigned.append(best_site)
            if first_2q[q] is not None and first_2q[q] <= self.lookahead:
                planned.append(
                    (best_site[0], nearest_ent[best_site][0],
                     best_site[1], nearest_ent[best_site][1])
                )

    # ── geometric helpers ─────────────────────────────────────────────
    @staticmethod
    def _compatible(a, b):
        if a[0] == b[0] and a[1] != b[1]: return False
        if a[1] == b[1] and a[0] != b[0]: return False
        if a[0] < b[0] and a[1] >= b[1]: return False
        if a[0] > b[0] and a[1] <= b[1]: return False
        if a[2] == b[2] and a[3] != b[3]: return False
        if a[3] == b[3] and a[2] != b[2]: return False
        if a[2] < b[2] and a[3] >= b[3]: return False
        if a[2] > b[2] and a[3] <= b[3]: return False
        return True

    def _pair_status(self, site):
        for p0, p1 in self.all_pairs:
            if site in (p0, p1):
                in_mapping = p0 in self.current_mapping and p1 in self.current_mapping
                return 2 if in_mapping else 1
        return -1

    def _find_other(self, site):
        for p0, p1 in self.all_pairs:
            if site == p0: return p1
            if site == p1: return p0
        return None

    # ── per-stage placing ─────────────────────────────────────────────
    def place(self, stage_idx: int) -> list[tuple[float, float]]:
        """Return updated mapping for this stage — Eq.15 decision + pair matching."""
        gates = self.list_full_gates[stage_idx]
        gate_qubits_2q = {q for pair in gates for q in pair if pair[0] != pair[1]}
        gate_qubits_1q = {q for pair in gates for q in pair if pair[0] == pair[1]}
        num_stages = len(self.list_full_gates)
        self._planned_vectors = []

        # ── Eq.15: idle qubit stay-or-move ──
        for q in range(self.n_q):
            if self.current_mapping[q] not in self.ent_slm_sites:
                continue
            if q in gate_qubits_2q:
                continue

            # Find next 2q stage for this qubit
            next_2q = None
            for s in range(stage_idx + 1, num_stages):
                for q0, q1 in self.list_full_gates[s]:
                    if q0 != q1 and q in (q0, q1):
                        next_2q = s
                        break
                if next_2q is not None:
                    break

            idle_end = next_2q if next_2q is not None else num_stages
            n_transfers = 2 if next_2q is None else 4
            crosstalk_stages = max(0, idle_end - stage_idx)

            # Costs
            crosstalk_cost = crosstalk_stages * (-math.log(self.fidelity_2q_idle))
            transfer_cost = n_transfers * (-math.log(self.fidelity_atom_transfer))

            # Find best storage site
            original = self.initial_mapping[q]
            candidates = []
            if original in self.stg_slm_sites and not any(
                self.current_mapping[i] == original for i in range(self.n_q) if i != q
            ):
                candidates.append(original)
            else:
                candidates.extend(
                    s for s in self.stg_slm_sites
                    if not any(self.current_mapping[i] == s for i in range(self.n_q) if i != q)
                )
            if not candidates:
                continue

            best = min(candidates, key=lambda s: math.dist(s, self.current_mapping[q]))
            dist_out = math.dist(self.current_mapping[q], best)
            approx_move_time = 0.5 * n_transfers * movement_duration_um(dist_out)
            decoherence_cost = (self.n_q - 1) * approx_move_time / self.time_coherence

            move_cost = transfer_cost + self.alpha * decoherence_cost

            if self.routing_strategy == "always_move":
                self._move_to_zone(q, "storage")
            elif self.routing_strategy == "always_stay":
                pass
            elif crosstalk_cost > move_cost:
                self._move_to_zone(q, "storage")

            # Return to original trap after last 2q
            if (self.current_mapping[q] in self.stg_slm_sites
                and self.current_mapping[q] != self.initial_mapping[q]
                and q not in gate_qubits_2q):
                has_future = any(
                    q in {qq for pair in self.list_full_gates[s] for qq in pair if pair[0] != pair[1]}
                    for s in range(stage_idx + 1, num_stages)
                )
                if not has_future:
                    if not any(self.current_mapping[i] == self.initial_mapping[q]
                               for i in range(self.n_q) if i != q):
                        self.current_mapping[q] = self.initial_mapping[q]

        # ── Pair matching for 2q gates ──
        for q0, q1 in gates:
            if q0 == q1:
                continue
            if ((self.current_mapping[q0], self.current_mapping[q1]) in self.all_pairs
                or (self.current_mapping[q1], self.current_mapping[q0]) in self.all_pairs):
                continue

            if self._pair_status(self.current_mapping[q0]) == 1:
                other = self._find_other(self.current_mapping[q0])
                if other is not None:
                    self._commit(q1, other)
            elif self._pair_status(self.current_mapping[q1]) == 1:
                other = self._find_other(self.current_mapping[q1])
                if other is not None:
                    self._commit(q0, other)
            else:
                # Both need new pair — find closest available
                avail = [(p0, p1) for p0, p1 in self.all_pairs
                         if p0 not in self.current_mapping and p1 not in self.current_mapping]
                best_rank = None
                best_pair = None
                for p0, p1 in avail:
                    d1 = math.dist(p0, self.current_mapping[q0]) + math.dist(p1, self.current_mapping[q1])
                    d2 = math.dist(p1, self.current_mapping[q0]) + math.dist(p0, self.current_mapping[q1])
                    score = min(d1, d2)
                    if best_rank is None or score < best_rank:
                        best_rank = score
                        best_pair = (p0, p1) if d1 < d2 else (p1, p0)
                if best_pair is not None:
                    self._commit(q0, best_pair[0])
                    self._commit(q1, best_pair[1])

        return self.current_mapping

    # ── move helpers ──────────────────────────────────────────────────
    def _move_to_zone(self, q: int, zone: str):
        if zone == "storage":
            original = self.initial_mapping[q]
            available = [s for s in self.stg_slm_sites
                         if not any(self.current_mapping[i] == s for i in range(self.n_q) if i != q)]
            if original in available:
                self._commit(q, original)
            elif available:
                best = min(available, key=lambda s: math.dist(s, self.current_mapping[q]))
                self._commit(q, best)
        elif zone == "entanglement":
            available = [s for s in self.ent_slm_sites
                         if self._pair_status(s) == 0]
            if available:
                best = min(available, key=lambda s: math.dist(s, self.current_mapping[q]))
                self._commit(q, best)

    def _commit(self, q: int, target: tuple):
        src = self.current_mapping[q]
        if src == target:
            return
        vector = (src[0], target[0], src[1], target[1])
        self._planned_vectors.append(vector)
        self.current_mapping[q] = target
