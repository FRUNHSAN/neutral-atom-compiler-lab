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
    _f6_formal_no_literals(constraints, warnings)

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

    # ── S10: Reasoning chain integrity ────────────────
    _s10_chain_integrity(project_root, constraints, all_boundaries, all_bridges, failures, info)

    # ── W: Check field compliance (§10.3) ──────────────
    _w1_check_field_required(constraints, warnings)
    _w2_check_fn_resolvable(constraints, project_root, warnings)

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


def _f6_formal_no_literals(constraints, warnings):
    """F6: formal 字段不应包含参数数值——数字属于 instance-space 或 boundary。

    扫 formal 字段中看起来像参数值的数字字面量（= 数字 或 比较符 + 非0/1数字）。
    0 和 1 豁免——它们是语义常数（零违反、单位概率），不是参数。
    Protocol 8（约束与求解器分离）。
    """
    import re
    # 匹配: = 数字, ≤ 数字, ≥ 数字, < 数字, > 数字
    # 豁免: 0, 0.0, 1, 1.0（语义常数）
    # 豁免: 数字后紧跟 √ π e（数学结构常数，非参数）
    pattern = re.compile(r'[=<≥≤>]\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)\s*(?!√|π|e)')
    for cid, c in constraints.items():
        formal = c.formal
        matches = pattern.findall(formal)
        for m in matches:
            try:
                val = float(m)
                if val == 0.0 or val == 1.0:
                    continue
                warnings.append(
                    f"F6: '{cid}' formal 含参数数值 '{m}'——"
                    f"数值应属于 instance-space 或 boundary，不属于 constraint"
                )
                break  # 一个约束只报一次
            except ValueError:
                pass


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


# ── S10: Reasoning chain integrity ─────────────────────

def _parse_chain_frontmatter(filepath: str) -> dict | None:
    """Extract YAML frontmatter from a Markdown chain file."""
    import yaml
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return None


def _check_one_chain_registry(
    chains_dir: str, index_path: str, label: str,
    constraints, boundaries, bridges,
    failures, info,
    private_ids: set,    # public chains must not reference these
):
    """Check one (index, chains_dir) pair. label = 'public' or 'private'.

    Returns (index_chains dict, chain_files dict).
    """
    import yaml

    if not os.path.isdir(chains_dir):
        return {}, {}

    # Load index
    index_data = {}
    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as f:
                index_data = yaml.safe_load(f) or {}
        except Exception:
            info.append(f"S10: {label} index 解析失败")
            return {}, {}

    index_chains = {c["chain_id"]: c for c in index_data.get("chains", [])}

    # Collect chain files (skip _TEMPLATE.md)
    chain_files = {}
    for fname in sorted(os.listdir(chains_dir)):
        if fname.startswith("_") or not fname.endswith(".md"):
            continue
        fpath = os.path.join(chains_dir, fname)
        fm = _parse_chain_frontmatter(fpath)
        if fm and fm.get("chain_id"):
            cid = fm["chain_id"]
            chain_files[cid] = {"path": fpath, "fm": fm}

    is_public = (label == "public")

    # (a) Chain file → in index
    for cid in chain_files:
        if cid not in index_chains:
            failures.append(f"S10(a): {label} 链文件 '{cid}' 不在 {label} index 中")

    # (b) Index entry → chain file exists
    for cid in index_chains:
        if cid not in chain_files:
            if is_public:
                failures.append(f"S10(b): 公开链 '{cid}' 文件不存在——应被 git 追踪")
            else:
                info.append(f"S10(b): 私有链 '{cid}' 文件不存在（gitignored，预期现象）")

    # (f) Public chain's related → must not reference private chain IDs
    if is_public and private_ids:
        for cid in chain_files:
            fm = chain_files[cid]["fm"]
            related = fm.get("related", []) or []
            for ref_id in related:
                if ref_id in private_ids:
                    failures.append(f"S10(f): 公开链 '{cid}' related 引用了私有链 '{ref_id}'——公开链不能依赖私有链")

    return index_chains, chain_files


def _s10_chain_integrity(project_root, constraints, boundaries, bridges, failures, info):
    """S10: Check reasoning chain integrity (public + private).

    (a) Every chain file → present in its index
    (b) Every index entry → chain file exists (public: FAIL, private: FYI)
    (c) Active chain files.code / files.experiments → paths exist
    (d) Active chain files.constraints / files.boundaries / files.bridges → IDs exist
    (e) Active chain produces_invariants / produces_constraints → IDs in registry
    (f) Public chain's related → must not reference private chain IDs
    """
    base = os.path.join(project_root, ".ai_reasoning")

    # Scan private first — collect private chain IDs for cross-reference check
    _, private_files = _check_one_chain_registry(
        os.path.join(base, "chains_private"),
        os.path.join(base, "index_private.yaml"),
        "private", constraints, boundaries, bridges,
        failures, info, set(),
    )
    private_ids = set(private_files.keys())

    # Scan public — pass private_ids for rule (f)
    _, public_files = _check_one_chain_registry(
        os.path.join(base, "chains"),
        os.path.join(base, "index.yaml"),
        "public", constraints, boundaries, bridges,
        failures, info, private_ids,
    )

    # Merge for (c)-(e) checks
    all_chain_files = {}
    all_chain_files.update(private_files)
    all_chain_files.update(public_files)

    # (c)-(e) Per active chain checks
    valid_cids = set(constraints.keys())
    valid_bids = set(boundaries.keys())
    valid_brids = set(bridges.keys())
    all_inv_ids = set(constraints.keys())

    for cid, entry in all_chain_files.items():
        fm = entry["fm"]
        status = fm.get("status", "draft")

        if status in ("active", "reverted"):
            files = fm.get("files", {})
            if isinstance(files, dict):
                for cat in ("code", "experiments"):
                    for fpath in files.get(cat, []) or []:
                        abspath = os.path.join(project_root, fpath)
                        if not os.path.exists(abspath):
                            info.append(f"S10(c): 链 '{cid}' status={status}, files.{cat}='{fpath}' 不存在（私有仓库预期现象，或建议检查是否需标记 reverted/archived）")

                for ref_id in files.get("constraints", []) or []:
                    if ref_id not in valid_cids:
                        failures.append(f"S10(d): 链 '{cid}' files.constraints 引用不存在的 '{ref_id}'")
                for ref_id in files.get("boundaries", []) or []:
                    if ref_id not in valid_bids:
                        failures.append(f"S10(d): 链 '{cid}' files.boundaries 引用不存在的 '{ref_id}'")
                for ref_id in files.get("bridges", []) or []:
                    if ref_id not in valid_brids:
                        failures.append(f"S10(d): 链 '{cid}' files.bridges 引用不存在的 '{ref_id}'")

            for inv_id in fm.get("produces_invariants", []) or []:
                if inv_id not in all_inv_ids:
                    info.append(f"S10(e): 链 '{cid}' produces_invariants 引用未注册的 '{inv_id}'")
            for con_id in fm.get("produces_constraints", []) or []:
                if con_id not in valid_cids:
                    info.append(f"S10(e): 链 '{cid}' produces_constraints 引用未注册的 '{con_id}'")

    n_public = len(public_files)
    n_private = len(private_files)
    info.append(f"S10: {n_public} 条公开链 + {n_private} 条私有链 = {n_public + n_private} total")


# ── I1-I4: Info ─────────────────────────────────────────

# ── W1-W2: Check field compliance (§10.3) ──────────────

def _w1_check_field_required(constraints, warnings):
    """W1: rigidity=hard + stage≥enforced → check 字段必须非空."""
    for cid, c in constraints.items():
        if c.rigidity.value == "hard" and c.stage.value in ("enforced", "implemented"):
            if not c.check:
                warnings.append(
                    f"W1: constraint '{cid}' is hard+enforced but has no check field. "
                    f"Add 'check: {{fn: domain.formulas.xxx.fn_name, on: each_xxx}}' "
                    f"to make the formal executable."
                )


def _w2_check_fn_resolvable(constraints, project_root, warnings):
    """W2: check.fn 路径可解析，模块存在且函数可导入."""
    for cid, c in constraints.items():
        if not c.check or not c.check.get("fn"):
            continue
        fn_ref = c.check["fn"]  # e.g. "domain.formulas.aod.validate_row_direction"
        parts = fn_ref.split(".")
        if len(parts) < 2:
            warnings.append(f"W2: '{cid}' check.fn '{fn_ref}' — invalid format, expected module.path.function")
            continue
        # Try to import the module
        mod_path = ".".join(parts[:-1])
        fn_name = parts[-1]
        mod_file = parts[-2] if len(parts) >= 2 else ""
        mod_full = os.path.join(project_root, *mod_path.split(".")) + ".py"
        if not os.path.exists(mod_full):
            warnings.append(
                f"W2: '{cid}' check.fn '{fn_ref}' — module file not found: {mod_full}"
            )
        else:
            try:
                mod = __import__(mod_path, fromlist=[fn_name])
                if not hasattr(mod, fn_name):
                    warnings.append(
                        f"W2: '{cid}' check.fn '{fn_ref}' — function '{fn_name}' "
                        f"not found in module '{mod_path}'"
                    )
            except ImportError as e:
                warnings.append(
                    f"W2: '{cid}' check.fn '{fn_ref}' — cannot import: {e}"
                )


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

    # Write .stale.json snapshot for time-series tracking (P6 — Doc 32)
    try:
        from framework.stale_snapshot import collect_snapshot, save_snapshot, archive_snapshot, cleanup_history
        snap = collect_snapshot(root)
        save_snapshot(root, snap)
        archive_snapshot(root, snap)
        cleanup_history(root)
    except Exception:
        pass  # stale snapshot is best-effort; never block check.py exit

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
