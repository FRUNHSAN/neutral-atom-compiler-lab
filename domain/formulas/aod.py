"""AOD physics validation — row/column direction + path crossing.

Referenced by:
    C-qc-aod-routing.check.fn
    C-qc-parking.check.fn
"""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    passed: bool
    reason: str = ""
    violations: list[str] = field(default_factory=list)


def validate_row_direction(instructions: list[dict],
                            parking_dist: float = 1.0) -> CheckResult:
    """同行 atom 必须同方向搬运。违反 → AOD 物理上不可行。

    C-qc-aod-routing: same-row atoms move with same dx sign.
    """
    violations = []
    # Collect all moves by row
    for idx, ins in enumerate(instructions):
        if ins["type"] not in ("BigMove", "Park"):
            continue
        rows: dict[int, list[tuple[int, float, float]]] = {}
        for loc in ins.get("locs", []):
            xb = loc.get("x_begin", 0); xe = loc.get("x_end", xb)
            yb = loc.get("y_begin", 0); ye = loc.get("y_end", yb)
            if (xb, yb) == (xe, ye):
                continue  # not a move
            dx = xe - xb; dy = ye - yb
            if dx != 0:
                row_key = int(yb)
                rows.setdefault(row_key, []).append((loc["id"], dx, dy))
            if dy != 0:
                col_key = int(xb)
                rows.setdefault(col_key + 10000, []).append((loc["id"], dx, dy))

        for key, moves in rows.items():
            if len(moves) <= 1:
                continue
            signs = {1 if m[1] > 0 else (-1 if m[1] < 0 else 0) for m in moves}
            if len(signs) > 1:
                ids = [m[0] for m in moves]
                violations.append(
                    f"ins[{idx}] {ins['type']}: qubits {ids} "
                    f"in same row/col have conflicting dx signs: {signs}"
                )

    return CheckResult(
        passed=len(violations) == 0,
        reason="AOD row/column direction violation" if violations else "",
        violations=violations,
    )


def detect_path_crossing(instructions: list[dict],
                          parking_dist: float = 1.0) -> CheckResult:
    """两条搬运路径交叉 → 至少一方必须有 parking。

    C-qc-parking: atom trajectories cannot overlap at any time.
    """
    violations = []
    for idx, ins in enumerate(instructions):
        if ins["type"] not in ("BigMove", "Park"):
            continue
        move_vecs = []
        for loc in ins.get("locs", []):
            xb = loc.get("x_begin", 0); xe = loc.get("x_end", xb)
            yb = loc.get("y_begin", 0); ye = loc.get("y_end", yb)
            if (xb, yb) == (xe, ye):
                continue
            move_vecs.append((loc["id"], xb, xe, yb, ye))

        for i in range(len(move_vecs)):
            for j in range(i + 1, len(move_vecs)):
                qi, xi1, xi2, yi1, yi2 = move_vecs[i]
                qj, xj1, xj2, yj1, yj2 = move_vecs[j]
                # Check if paths cross in x-y plane
                if _paths_cross(xi1, xi2, yi1, yi2, xj1, xj2, yj1, yj2):
                    violations.append(
                        f"ins[{idx}] {ins['type']}: qubits {qi}↔{qj} "
                        f"paths cross at stage {ins.get('stage', '?')}"
                    )

    return CheckResult(
        passed=len(violations) == 0,
        reason="Path crossing without parking" if violations else "",
        violations=violations,
    )


def _paths_cross(x1_start, x1_end, y1_start, y1_end,
                  x2_start, x2_end, y2_start, y2_end) -> bool:
    """Simple 2D path crossing check for grid-based moves."""
    # Only check if both are non-trivial moves
    if (x1_start, y1_start) == (x1_end, y1_end):
        return False
    if (x2_start, y2_start) == (x2_end, y2_end):
        return False
    # Same column: if y ranges overlap and x changes in opposite directions
    if x1_start == x2_start:
        y1_range = (min(y1_start, y1_end), max(y1_start, y1_end))
        y2_range = (min(y2_start, y2_end), max(y2_start, y2_end))
        if y1_range[0] <= y2_range[1] and y2_range[0] <= y1_range[1]:
            return True
    # Same row: if x ranges overlap and y changes in opposite directions
    if y1_start == y2_start:
        x1_range = (min(x1_start, x1_end), max(x1_start, x1_end))
        x2_range = (min(x2_start, x2_end), max(x2_start, x2_end))
        if x1_range[0] <= x2_range[1] and x2_range[0] <= x1_range[1]:
            return True
    return False
