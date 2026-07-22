"""Crosstalk constraint validation — idle qubit entanglement zone exposure.

Referenced by:
    C-qc-crosstalk.check.fn
"""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    passed: bool
    reason: str = ""
    violations: list[str] = field(default_factory=list)


def entanglement_zone_only(instructions: list[dict],
                            ent_site_y_min: float = 0.0) -> CheckResult:
    """只有纠缠区内的空闲 qubit 才应计入串扰暴露。

    C-qc-crosstalk: idle atoms in entanglement zone exposed to global Rydberg laser.
    Storage zone atoms are physically shielded and should NOT be counted.
    """
    violations = []
    for idx, ins in enumerate(instructions):
        if ins["type"] != "Crosstalk":
            continue
        for loc in ins.get("locs", []):
            y = loc.get("y", 0)
            if y < ent_site_y_min:
                violations.append(
                    f"ins[{idx}] Crosstalk: qubit {loc['id']} at y={y} < "
                    f"entanglement zone edge ({ent_site_y_min}) — "
                    f"should not be counted as crosstalk exposure"
                )

    return CheckResult(
        passed=len(violations) == 0,
        reason="Storage zone qubit incorrectly counted as crosstalk" if violations else "",
        violations=violations,
    )
