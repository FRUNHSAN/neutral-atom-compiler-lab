"""
check.py — 量子编译器域约束一致性检查。

30 条规则，分 5 组：
  F  (Formal)        — 约束层结构和语义
  B  (Boundary)      — 边界层与约束层链接
  BR (Bridge)        — 桥声明完整性
  S  (Stage)         — 阶段门规则
  I  (Integration)   — 跨编译器交叉验证

用法: python framework/check.py .
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from framework.io import load_all_constraints, load_all_boundaries, load_all_bridges
from framework.schema import Stage


def check_all(project_root: str) -> tuple[list[str], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    constraints_dir = os.path.join(project_root, "constraints")
    boundaries_dir = os.path.join(project_root, "boundaries")
    bridges_dir = os.path.join(project_root, "bridges")

    constraints = load_all_constraints(constraints_dir)
    boundaries = load_all_boundaries(boundaries_dir)
    bridges = load_all_bridges(bridges_dir)

    # ── F: Formal 层 ────────────────────────────────
    _f1_id_format(constraints, failures)
    _f2_stage_legal(constraints, failures)
    _f3_derives_dag(constraints, failures)
    _f4_formal_nonempty(constraints, failures)
    _f5_domain_tags(constraints, failures)

    # ── B: Boundary 层 ──────────────────────────────
    _b1_boundary_links(constraints, boundaries, failures)
    _b2_cost_terms_defined(boundaries, failures)
    _b3_assumptions_present(boundaries, warnings)

    # ── BR: Bridge 层 ───────────────────────────────
    _br1_source_target_exist(bridges, constraints, boundaries, failures)
    _br2_coupled_has_solver(bridges, failures)
    _br3_bridge_tags(bridges, failures)

    # ── S: Stage 门 ─────────────────────────────────
    _s1_no_skip_stage(constraints, failures)

    # ── I: Integration ──────────────────────────────
    _i1_hard_constraint_coverage(constraints, boundaries, info)
    _i2_bridge_sensitivity(bridges, info)

    return failures, warnings, info


# ── F1-F5 ───────────────────────────────────────────────

def _f1_id_format(constraints, failures):
    seen = set()
    for cid in constraints:
        if not cid.startswith("C-qc-"):
            failures.append(f"F1: ID '{cid}' 不符合 C-qc-* 格式")
        if cid in seen:
            failures.append(f"F1: ID '{cid}' 重复")
        seen.add(cid)

def _f2_stage_legal(constraints, failures):
    for cid, c in constraints.items():
        if c.stage not in Stage:
            failures.append(f"F2: '{cid}' stage={c.stage.value} 不合法")

def _f3_derives_dag(constraints, failures):
    adj = {cid: set(c.derives_from) for cid, c in constraints.items()}
    visited, rec = set(), set()
    def dfs(n):
        visited.add(n); rec.add(n)
        for p in adj.get(n, set()):
            if p not in constraints:
                failures.append(f"F3: '{n}' derives_from 不存在的 '{p}'")
            elif p not in visited:
                if dfs(p): return True
            elif p in rec:
                failures.append(f"F9: DAG 有环: '{n}' → '{p}'")
                return True
        rec.discard(n); return False
    for cid in constraints:
        if cid not in visited: dfs(cid)

def _f4_formal_nonempty(constraints, failures):
    for cid, c in constraints.items():
        if not c.formal or len(c.formal.strip()) < 10:
            failures.append(f"F4: '{cid}' formal 为空或过短")

def _f5_domain_tags(constraints, failures):
    for cid, c in constraints.items():
        if not c.domain_tags:
            failures.append(f"F5 (F8): '{cid}' 缺少 domain_tags")

# ── B1-B3 ───────────────────────────────────────────────

def _b1_boundary_links(constraints, boundaries, failures):
    cids = set(constraints.keys())
    for bid, b in boundaries.items():
        if b.constraint and b.constraint not in cids:
            failures.append(f"B1: 边界 '{bid}' 引用不存在的约束 '{b.constraint}'")

def _b2_cost_terms_defined(boundaries, failures):
    for bid, b in boundaries.items():
        defined = set(b.cost_terms.keys())
        for gn, terms in b.cost_groups.items():
            for t in terms:
                if t not in defined:
                    failures.append(
                        f"B2: 边界 '{bid}' cost_group '{gn}' "
                        f"引用未定义的 cost_term '{t}'")

def _b3_assumptions_present(boundaries, warnings):
    for bid, b in boundaries.items():
        if not b.assumptions:
            warnings.append(f"B3: 边界 '{bid}' 未声明 assumptions")

# ── BR1-BR3 ─────────────────────────────────────────────

def _br1_source_target_exist(bridges, constraints, boundaries, failures):
    cids = set(constraints.keys())
    cg_ids = set()
    for b in boundaries.values():
        cg_ids.update(b.cost_groups.keys())
    valid = cids | cg_ids
    for brid, br in bridges.items():
        if br.source not in valid:
            failures.append(f"BR1: 桥 '{brid}' source='{br.source}' 不存在")
        if br.target not in valid:
            failures.append(f"BR1: 桥 '{brid}' target='{br.target}' 不存在")

def _br2_coupled_has_solver(bridges, failures):
    for brid, br in bridges.items():
        if br.coupled and br.resolve_fn.value != "solver":
            failures.append(
                f"BR2: 耦合桥 '{brid}' resolve_fn 应为 solver（当前 {br.resolve_fn.value}）")

def _br3_bridge_tags(bridges, failures):
    for brid, br in bridges.items():
        if not br.domain_tags:
            failures.append(f"BR3: 桥 '{brid}' 缺少 domain_tags")

# ── S1 ──────────────────────────────────────────────────

def _s1_no_skip_stage(constraints, failures):
    for cid, c in constraints.items():
        for pid in c.derives_from:
            if pid in constraints:
                if not constraints[pid].stage.can_jump_to(c.stage):
                    failures.append(
                        f"S1 (F10): '{cid}' stage={c.stage.value} "
                        f"但父约束 '{pid}' stage={constraints[pid].stage.value}（跳级）")

# ── I1-I2 ───────────────────────────────────────────────

def _i1_hard_constraint_coverage(constraints, boundaries, info):
    covered = {b.constraint for b in boundaries.values() if b.constraint}
    for cid, c in constraints.items():
        if c.rigidity.value == "hard" and cid not in covered:
            info.append(f"I1: 硬约束 '{cid}' 尚无 boundary 覆盖")

def _i2_bridge_sensitivity(bridges, info):
    for brid in bridges:
        info.append(f"I2: 桥 '{brid}' — 敏感性待实验确认")


# ── CLI ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python framework/check.py <项目目录>")
        sys.exit(1)

    root = sys.argv[1]
    failures, warnings, info = check_all(root)

    print("=" * 60)
    print(f"  约束一致性检查 — {root}")
    print("=" * 60)

    for label, items, icon in [
        ("FAIL", failures, "[FAIL]"),
        ("WARN", warnings,  "[WARN]"),
        ("FYI",  info,      "[FYI] "),
    ]:
        if items:
            print(f"\n  {icon} {label}: {len(items)} issues")
            for item in items:
                print(f"    {item}")

    if failures:
        print(f"\n  FAIL: {len(failures)}")
    else:
        print(f"\n  PASS: 0 FAIL")
    print(f"  WARN: {len(warnings)}")
    print(f"  FYI:  {len(info)}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
