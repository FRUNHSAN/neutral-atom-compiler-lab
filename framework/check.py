"""
check.py — 约束式工程一致性检查（量子编译器域）

规则分组:
  F  (Formal)           — domain/constraints/ 内部
  BD (Bridge Declaration) — domain/bridge-declarations/ 内部
  B  (Boundary)         — instances/*/boundaries/ ↔ domain
  BR (Bridge)           — instances/*/bridges/ ↔ domain + boundaries
  IS (Instance-Space)   — instance-space/ 内部
  D  (Declaration)      — instance-space/declarations/ ↔ instances

用法: python framework/check.py .
"""
from __future__ import annotations
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from framework.io import load_all_constraints, load_all_boundaries, load_all_bridges
from framework.schema import Stage, BridgeLayer


def check_all(project_root: str) -> tuple[list[str], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    # Domain paths
    constraints_dir = os.path.join(project_root, "domain", "constraints")
    bd_dir = os.path.join(project_root, "domain", "bridge-declarations")

    # Instance paths
    instances_dir = os.path.join(project_root, "instances")

    # Instance-space paths
    ispace_dir = os.path.join(project_root, "instance-space")

    # Load
    constraints = load_all_constraints(constraints_dir)
    declarations = load_all_bridges(bd_dir) if os.path.isdir(bd_dir) else {}

    # Collect per-instance boundaries and bridges
    instance_boundaries: dict[str, dict] = {}
    instance_bridges: dict[str, dict] = {}
    instance_names: list[str] = []
    if os.path.isdir(instances_dir):
        for iname in os.listdir(instances_dir):
            ipath = os.path.join(instances_dir, iname)
            if not os.path.isdir(ipath):
                continue
            instance_names.append(iname)
            bnd_dir = os.path.join(ipath, "boundaries")
            brg_dir = os.path.join(ipath, "bridges")
            instance_boundaries[iname] = load_all_boundaries(bnd_dir) if os.path.isdir(bnd_dir) else {}
            instance_bridges[iname] = load_all_bridges(brg_dir) if os.path.isdir(brg_dir) else {}

    all_boundaries = {}
    for ib in instance_boundaries.values():
        all_boundaries.update(ib)
    all_bridges = {}
    for ib in instance_bridges.values():
        all_bridges.update(ib)

    # ── F: Domain constraints ─────────────────────────
    _f1_id_format(constraints, failures)
    _f2_stage_legal(constraints, failures)
    _f3_derives_dag(constraints, failures)
    _f4_formal_nonempty(constraints, failures)
    _f5_domain_tags(constraints, failures)

    # ── BD: Domain bridge declarations ────────────────
    _bd1_declaration_no_resolve(declarations, failures)

    # ── B: Boundary ↔ constraint ─────────────────────
    _b1_boundary_links(constraints, all_boundaries, failures)
    _b2_cost_terms_defined(all_boundaries, failures)
    _b3_assumptions_present(all_boundaries, warnings)

    # ── BR: Instance bridges ─────────────────────────
    _br1_source_target_exist(all_bridges, constraints, all_boundaries, failures)
    _br2_coupled_has_solver(all_bridges, failures)
    _br3_bridge_tags(all_bridges, failures)
    _br4_layer_consistency(all_bridges, failures)

    # ── IS: Instance-space ───────────────────────────
    _is1_ruler_exists(project_root, ispace_dir, failures)
    _is2_tolerance_consistent(project_root, ispace_dir, failures)

    # ── D: Declarations ──────────────────────────────
    _d1_declaration_refs_valid(project_root, ispace_dir, instance_names, all_bridges, constraints, failures)

    # ── S: Stage gate ────────────────────────────────
    _s1_no_skip_stage(constraints, failures)

    # ── I: Info ──────────────────────────────────────
    _i1_hard_constraint_coverage(constraints, all_boundaries, info)
    _i2_bridge_sensitivity(all_bridges, info)
    _i3_instance_bridge_coverage(instance_names, instance_bridges, instance_boundaries, info)
    _i4_declaration_count(declarations, info)

    return failures, warnings, info


# ── F1-F5: Domain constraints ───────────────────────────

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
            failures.append(f"F5: '{cid}' 缺少 domain_tags")


# ── BD1: Bridge declarations ────────────────────────────

def _bd1_declaration_no_resolve(declarations, failures):
    for did, d in declarations.items():
        if d.layer != BridgeLayer.DECLARATION:
            failures.append(f"BD1: '{did}' 在 domain/bridge-declarations/ 但 layer != declaration")
        if d.resolve_fn is not None:
            failures.append(f"BD1: 声明桥 '{did}' 不应包含 resolve_fn（声明不包含解法）")


# ── B1-B3: Boundaries ──────────────────────────────────

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
                    failures.append(f"B2: 边界 '{bid}' cost_group '{gn}' 引用未定义的 cost_term '{t}'")

def _b3_assumptions_present(boundaries, warnings):
    for bid, b in boundaries.items():
        if not b.assumptions:
            warnings.append(f"B3: 边界 '{bid}' 未声明 assumptions")


# ── BR1-BR4: Instance bridges ──────────────────────────

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
        if br.mode.value == "coupled" and (br.resolve_fn is None or br.resolve_fn.value != "solver"):
            failures.append(f"BR2: 耦合桥 '{brid}' resolve_fn 应为 solver")

def _br3_bridge_tags(bridges, failures):
    for brid, br in bridges.items():
        if not br.domain_tags:
            failures.append(f"BR3: 桥 '{brid}' 缺少 domain_tags")

def _br4_layer_consistency(bridges, failures):
    for brid, br in bridges.items():
        if br.layer != BridgeLayer.INSTANCE:
            failures.append(f"BR4: 实例桥 '{brid}' layer 应为 instance")
        if br.declares and not br.declares.startswith("BD-"):
            failures.append(f"BR4: 桥 '{brid}' declares='{br.declares}' 不符合 BD-* 格式")


# ── IS1-IS2: Instance-space ─────────────────────────────

def _is1_ruler_exists(project_root, ispace_dir, failures):
    if not os.path.isdir(ispace_dir):
        return
    for sname in os.listdir(ispace_dir):
        spath = os.path.join(ispace_dir, sname)
        if not os.path.isdir(spath):
            continue
        proto = os.path.join(spath, "protocol.yaml")
        if not os.path.exists(proto):
            failures.append(f"IS1: 实例空间 '{sname}' 缺少 protocol.yaml（无尺子 = 不是实例空间）")

def _is2_tolerance_consistent(project_root, ispace_dir, failures):
    import yaml
    for sname in os.listdir(ispace_dir) if os.path.isdir(ispace_dir) else []:
        spath = os.path.join(ispace_dir, sname)
        if not os.path.isdir(spath):
            continue
        proto = os.path.join(spath, "protocol.yaml")
        if not os.path.exists(proto):
            continue
        with open(proto, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        ruler = data.get("ruler", {})
        tol = ruler.get("tolerance", {})
        eqv = tol.get("equivalent", 0)
        notb = tol.get("notable", 0)
        if eqv >= notb:
            failures.append(f"IS2: 空间 '{sname}' tolerance.equivalent({eqv}) >= tolerance.notable({notb}) — 尺子不自洽")


# ── D1: Declarations ────────────────────────────────────

def _d1_declaration_refs_valid(project_root, ispace_dir, instance_names, bridges, constraints, failures):
    import yaml
    for sname in os.listdir(ispace_dir) if os.path.isdir(ispace_dir) else []:
        decl_dir = os.path.join(ispace_dir, sname, "declarations")
        if not os.path.isdir(decl_dir):
            continue
        for df in sorted(os.listdir(decl_dir)):
            if not df.endswith(".yaml"):
                continue
            with open(os.path.join(decl_dir, df), encoding="utf-8") as f:
                d = yaml.safe_load(f)

            # ruler ref
            ruler_ref = d.get("ruler", "")
            if ruler_ref and not os.path.exists(os.path.join(decl_dir, ruler_ref)):
                failures.append(f"D1: 声明 '{df}' ruler='{ruler_ref}' 文件不存在")

            # constraint ref
            c_ref = d.get("constraint", "")
            if c_ref and c_ref not in constraints:
                failures.append(f"D1: 声明 '{df}' constraint='{c_ref}' 不在 domain/constraints/ 里")

            # approaches
            for a in d.get("approaches", []):
                iname = a.get("instance", "")
                if iname and iname not in instance_names:
                    failures.append(f"D1: 声明 '{df}' 引用不存在的实例 '{iname}'")
                bridge_ref = a.get("bridge", "")
                if bridge_ref:
                    if iname in instance_names:
                        ib = {b.id for b in bridges.values()}
                        if bridge_ref not in ib and bridge_ref not in {b.id for b in bridges.values()}:
                            failures.append(f"D1: 声明 '{df}' 引用不存在的桥 '{bridge_ref}'")


# ── S1: Stage gate ──────────────────────────────────────

def _s1_no_skip_stage(constraints, failures):
    for cid, c in constraints.items():
        for pid in c.derives_from:
            if pid in constraints:
                if not constraints[pid].stage.can_jump_to(c.stage):
                    failures.append(f"S1 (F10): '{cid}' stage={c.stage.value} 跳级（父 '{pid}' stage={constraints[pid].stage.value}）")


# ── I1-I4: Info ─────────────────────────────────────────

def _i1_hard_constraint_coverage(constraints, boundaries, info):
    covered = {b.constraint for b in boundaries.values() if b.constraint}
    for cid, c in constraints.items():
        if c.rigidity.value == "hard" and cid not in covered:
            info.append(f"I1: 硬约束 '{cid}' 尚无 boundary 覆盖")

def _i2_bridge_sensitivity(bridges, info):
    for brid in bridges:
        info.append(f"I2: 桥 '{brid}' — 敏感性待实验确认")

def _i3_instance_bridge_coverage(instance_names, instance_bridges, instance_boundaries, info):
    for iname in instance_names:
        nb = len(instance_bridges.get(iname, {}))
        nbd = len(instance_boundaries.get(iname, {}))
        info.append(f"I3: 实例 '{iname}' — {nbd} 条边界, {nb} 座桥")

def _i4_declaration_count(declarations, info):
    if declarations:
        info.append(f"I4: domain/bridge-declarations/ — {len(declarations)} 座声明桥（Rule of Three: 出现三次才建）")
    else:
        info.append(f"I4: domain/bridge-declarations/ — 空（Rule of Three: 出现三次才建）")


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

    for label, items in [
        ("FAIL", failures),
        ("WARN", warnings),
        ("FYI",  info),
    ]:
        if items:
            print(f"\n  [{label}] {len(items)} issues:")
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
