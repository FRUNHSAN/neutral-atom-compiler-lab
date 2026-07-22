"""Fidelity simulator — walks instruction list, accumulates 5-channel fidelity.

Uses domain/formulas/fidelity.py for the unified cross-compiler fidelity model.
Parameters from B-nac-hardware (operation_fidelity, qubit_spec).
"""

import math
import numpy as np


class Simulator:
    """Roll up duration and multiplicative fidelity from instructions."""

    def __init__(self, instructions: list[dict], n_qubits: int,
                 n_1q: int, n_2q: int, architecture: dict | None = None):
        self.instructions = instructions
        self.n_q = n_qubits
        self.n_1q_gate = n_1q
        self.n_2q_gate = n_2q

        arch = architecture or {}
        op_fid = arch.get("operation_fidelity", {})
        op_dur = arch.get("operation_duration", {})
        qubit_spec = arch.get("qubit_spec", {})

        self.f_2q = op_fid.get("two_qubit_gate", 0.995)
        f2 = self.f_2q
        self.f_2q_idle = op_fid.get("two_qubit_gate_for_idle", 1.0 - (1.0 - f2) / 2.0)
        self.f_1q = op_fid.get("single_qubit_gate", 0.9997)
        self.f_tr = op_fid.get("atom_transfer", 0.999)
        self.T2 = qubit_spec.get("T2", 1.5e6)

        self.total_duration: float = 0.0
        self.fidelity_1q: float = 1.0
        self.fidelity_2q: float = 1.0
        self.fidelity_idle: float = 1.0
        self.fidelity_tr: float = 1.0
        self.fidelity_dec: float = 1.0
        self.fidelity_total: float = 1.0
        self.qubit_busy: list[float] = [0.0] * self.n_q

        self._simulate()

    def _simulate(self):
        for ins in self.instructions:
            t = ins["type"]
            dur = ins.get("duration", [0])
            qs = ins.get("qs", [])

            if t == "Init":
                continue
            elif t in ("Activate", "Deactivate"):
                self.total_duration += max(dur) if dur else 0
                self.fidelity_tr *= self.f_tr ** len(qs)
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0
            elif t == "BigMove":
                self.total_duration += max(dur) if dur else 0
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0
            elif t == "Park":
                self.total_duration += max(dur) if dur else 0
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0
            elif t == "1qGate":
                self.total_duration += max(dur) if dur else 0
                self.fidelity_1q *= self.f_1q ** len(ins.get("gates", qs))
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0
            elif t == "2qGate":
                self.total_duration += max(dur) if dur else 0
                self.fidelity_2q *= self.f_2q ** len(ins.get("gates", qs))
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0
            elif t == "Crosstalk":
                self.fidelity_idle *= self.f_2q_idle ** len(qs)
                for i, q in enumerate(qs):
                    self.qubit_busy[q] += dur[i] if i < len(dur) else 0

        # Decoherence: idle time per qubit
        for busy_t in self.qubit_busy:
            idle_t = self.total_duration - busy_t
            self.fidelity_dec *= math.exp(-idle_t / self.T2)

        self.fidelity_total = (
            self.fidelity_1q * self.fidelity_2q * self.fidelity_idle
            * self.fidelity_tr * self.fidelity_dec
        )

    def as_dict(self) -> dict:
        return {
            "total_fidelity": round(self.fidelity_total, 8),
            "fidelity_1q_gate": round(self.fidelity_1q, 8),
            "fidelity_2q_gate": round(self.fidelity_2q, 8),
            "fidelity_idle": round(self.fidelity_idle, 8),
            "fidelity_handover": round(self.fidelity_tr, 8),
            "fidelity_decoherence": round(self.fidelity_dec, 8),
            "total_duration": round(self.total_duration, 6),
            "n_1q_gate": self.n_1q_gate,
            "n_2q_gate": self.n_2q_gate,
        }
