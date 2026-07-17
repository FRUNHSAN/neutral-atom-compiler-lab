"""
io.py — YAML 加载 + 项目注册表构建。
"""
from __future__ import annotations
import yaml
from pathlib import Path
from framework.schema import (
    Constraint, Boundary, Bridge, CostTerm,
    Stage, Rigidity, BridgeType, ResolveFn, BridgeMode, BridgeLayer,
)


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_constraint(yaml_path: str) -> Constraint:
    d = load_yaml(yaml_path)
    return Constraint(
        id=d["id"], name=d["name"],
        stage=Stage(d["stage"]),
        formal=d.get("formal", ""),
        rigidity=Rigidity(d.get("rigidity", "soft")),
        domain_tags=d.get("domain_tags", []),
        G_C=d.get("G(C)", 0.0),
        derives_from=d.get("derives_from", []),
        status=d.get("status", "active"),
        ai_confidence=d.get("ai_confidence", ""),
        last_ai_review=d.get("last_ai_review", ""),
        ai_review_notes=d.get("ai_review_notes", ""),
    )


def load_boundary(yaml_path: str) -> Boundary:
    d = load_yaml(yaml_path)
    cost_terms = {}
    for tid, td in d.get("cost_terms", {}).items():
        cost_terms[tid] = CostTerm(
            formula=td.get("formula", ""),
            params=td.get("params", {}),
            description=td.get("description", ""),
        )
    return Boundary(
        id=d["id"], constraint=d.get("constraint", ""),
        implements_formal=d.get("implements_formal", ""),
        stage=Stage(d.get("stage", "reduced")),
        domain_tags=d.get("domain_tags", []),
        assumptions=d.get("assumptions", []),
        cost_terms=cost_terms,
        cost_groups=d.get("cost_groups", {}),
        discretization_gap=d.get("discretization_gap", ""),
    )


def load_bridge(yaml_path: str) -> Bridge:
    d = load_yaml(yaml_path)
    resolve_fn = d.get("resolve_fn", None)
    return Bridge(
        id=d["id"],
        type=BridgeType(d.get("type", "tension")),
        source=d.get("source", ""),
        target=d.get("target", ""),
        mediation=d.get("mediation", ""),
        resolve_fn=ResolveFn(resolve_fn) if resolve_fn else None,
        mode=BridgeMode(d.get("mode", "independent")),
        layer=BridgeLayer(d.get("layer", "instance")),
        declares=d.get("declares", ""),
        coupled=d.get("coupled", False),
        solver_timeout_ms=d.get("solver_timeout_ms", 50),
        solver_fallback=d.get("solver_fallback", ""),
        domain_tags=d.get("domain_tags", []),
    )


def load_all_constraints(constraints_dir: str) -> dict[str, Constraint]:
    constraints = {}
    for yf in sorted(Path(constraints_dir).glob("C-qc-*.yaml")):
        c = load_constraint(str(yf))
        constraints[c.id] = c
    return constraints


def load_all_boundaries(boundaries_dir: str) -> dict[str, Boundary]:
    boundaries = {}
    for yf in sorted(Path(boundaries_dir).glob("B-*.yaml")):
        b = load_boundary(str(yf))
        boundaries[b.id] = b
    return boundaries


def load_all_bridges(bridges_dir: str) -> dict[str, Bridge]:
    bridges = {}
    for yf in sorted(Path(bridges_dir).glob("BR-*.yaml")):
        b = load_bridge(str(yf))
        bridges[b.id] = b
    return bridges
