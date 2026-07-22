"""ASAP gate scheduler — groups flat CZ gate list into parallel stages.

Reads BR-asap-strategy for scheduling variant (separate/joint).
No hardcoded numerical parameters — all logic is structural.
"""


class Scheduler:
    """Build per-stage gate groups from a flat (q0, q1) gate list."""

    def __init__(self, g_q: list, n_qubits: int, strategy: str = "asap_separate"):
        """
        Args:
            g_q: Flat list of (q0, q1) — q0==q1 for 1-qubit gates.
            n_qubits: Number of logical qubits.
            strategy: ``asap_separate`` (default) or ``asap_joint``.
        """
        self.g_q = g_q
        self.n_q = n_qubits
        self.strategy = strategy
        self.stages: dict[int, dict] = {}
        self.num_stages: int = 0

        if strategy == "asap_separate":
            self._asap_separate()
        elif strategy == "asap_joint":
            self._asap_joint()
        else:
            raise ValueError(f"Unknown scheduling strategy: {strategy}")

    def _asap_separate(self):
        """Schedule 2q gates first by ASAP, then fit 1q gates around them."""
        qubit_stage = [0] * self.n_q
        stages: list[list[int]] = []

        # Phase 1: schedule 2q gates
        for i, (q0, q1) in enumerate(self.g_q):
            if q0 == q1:
                continue
            stage = max(qubit_stage[q0], qubit_stage[q1])
            while len(stages) <= stage:
                stages.append([])
            stages[stage].append(i)
            qubit_stage[q0] = qubit_stage[q1] = stage + 1

        # Phase 2: slot 1q gates
        prev_2q_stage: dict[int, int] = {}
        for stage_idx, gates in enumerate(stages):
            for gate_idx in gates:
                q0, q1 = self.g_q[gate_idx]
                prev_2q_stage[q0] = stage_idx
                prev_2q_stage[q1] = stage_idx

        for i, (q0, q1) in enumerate(self.g_q):
            if q0 != q1:
                continue  # already handled
            stage = max(prev_2q_stage.get(q0, -1), prev_2q_stage.get(q1, -1)) + 1
            while len(stages) <= stage:
                stages.append([])

            has_2q = any(self.g_q[j][0] != self.g_q[j][1] for j in stages[stage])
            if has_2q:
                stages.insert(stage, [i])
            else:
                stages[stage].append(i)

        self._build_stage_dict(stages)

    def _asap_joint(self):
        """Schedule all gates (1q and 2q) together by ASAP."""
        qubit_stage = [0] * self.n_q
        stages: list[list[int]] = []

        for i, (q0, q1) in enumerate(self.g_q):
            stage = max(qubit_stage[q0], qubit_stage[q1])
            while len(stages) <= stage:
                stages.append([])
            stages[stage].append(i)
            qubit_stage[q0] = qubit_stage[q1] = stage + 1

        self._build_stage_dict(stages)

    def _build_stage_dict(self, stages: list[list[int]]):
        """Convert stage list to structured dict."""
        self.num_stages = len(stages)
        self.stages = {}
        for sidx, gates in enumerate(stages):
            is_2q = all(self.g_q[g][0] != self.g_q[g][1] for g in gates)
            is_1q = all(self.g_q[g][0] == self.g_q[g][1] for g in gates)
            if is_2q:
                stype = "2qGate"
            elif is_1q:
                stype = "1qGate"
            else:
                stype = "mGate"
            self.stages[sidx] = {
                "type": stype,
                "idx": gates,
                "gates": [self.g_q[g] for g in gates],
            }

    def as_gate_list(self) -> list[list[tuple[int, int]]]:
        """Return stages as list of gate-pair lists (for placer consumption)."""
        return [self.stages[s]["gates"] for s in range(self.num_stages)]
