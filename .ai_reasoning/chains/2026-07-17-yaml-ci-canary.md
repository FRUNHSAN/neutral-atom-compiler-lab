---
chain_id: 2026-07-17-yaml-ci-canary
title: "YAML 约束层保留为 CI 金丝雀——不删、不绑实验、不扩展"
layer: L1
ternary_owner: agent
tags: [framework, yaml, ci, project-structure, cleanup]
status: active
created: 2026-07-17
supersedes: []
superseded_by: []
reverted_by: ""
related: []
files:
  constraints: ["domain/constraints/C-qc-*.yaml"]
  boundaries: ["instances/ZAP/boundaries/B-zap-hardware.yaml"]
  bridges: ["instances/ZAP/bridges/BR-*.yaml"]
  code: ["framework/check.py", "framework/io.py", "framework/schema.py"]
  experiments: []
produces_invariants: []
produces_constraints: []
cross_domain: false
domains_verified: []
---

# Context

基础清理时发现 13 个 YAML 文件（10 条约束 + 1 条边界 + 2 座桥）没有任何实验脚本读取它们。实验全部从 Python 源码直接 import 参数。这些 YAML 的唯一消费者是 `framework/check.py`——它做形式校验（ID 格式、DAG 无环、字段非空）。三个可选方案。

# Decision

**保留 YAML + check.py 不动。不往里面加新约束。不修 check 规则。不绑定实验脚本。当 CI 金丝雀——只要 `python framework/check.py .` 报 0 FAIL，就说明项目结构没被人不小心破坏。**

# Rationale

三个方案的权衡：

1. **删掉 YAML + check.py**：最干净，但丢了一个结构完整性嗅探器。哪天有人改了 schema.py 的字段名、删了某条约束的 formal、在桥 YAML 里写错了引用——没有人会注意到，因为没有消费者。check.py 虽然校验的是"没人读的数据"，但它校验的是"项目有没有人改坏了"。

2. **让实验脚本从 YAML 加载参数**：框架洁癖——参数确实应该从 YAML 来，但当前实验脚本已经稳定、参数少（就 5 个硬件默认值）、改动频率低。绑定 YAML 需要重构所有实验的 import 链，ROI 为负。

3. **保留当 CI 金丝雀（选择）**：零维护成本。check.py 已经写好了。13 个 YAML 的内容已经稳定。每次 `python framework/check.py . → 0 FAIL` 告诉我"项目的结构完整性还在"。哪天这 13 个 YAML 里需要填新内容时——比如 Rule of Three 触发、需要建第一座域级桥声明——再做决定要不要扩展。在那之前，它们是文档，不是工具。

核心判断：**check.py 的校验对象不是 YAML 的内容正确性（那取决于人），而是项目结构的完整性（那可以机械化）。** 只要 0 FAIL，任何结构破坏都会立刻被捕获。

# Alternatives

**方案 A：删 YAML + check.py**
- Pros：项目更干净，没有"仪式性"文件
- Cons：失去结构完整性嗅探；check.py 348 行全部白写；哪天想加回来成本高
- 拒绝原因：保留成本为零，删除成本不可逆

**方案 B：实验绑定 YAML**
- Pros：框架设计一致性，参数单源真理
- Cons：重构所有实验 import 链；当前实验已稳定，改动风险 > 收益
- 拒绝原因：12 周时间窗内 ROI 为负。等有新实验需要频繁调参数时再做

# Evidence

- `python framework/check.py .` 稳定输出 `PASS: 0 FAIL / 0 WARN / 12 FYI`（2026-07-17 验证）
- 所有 7 个实验脚本独立于 YAML 运行，0 破坏
- 删除 `src/nac_lab/` 重复文件后，check.py 仍然 0 FAIL——证明它的校验是结构性的，不依赖死代码

# Future Guidance

- 保持 YAML 内容和 check.py 规则不修改——否则金丝雀的基准线就变了
- Rule of Three 触发时（第三个编译器加入 → 同一对张力出现三次 → 建域级桥声明 BD-xxx），在 `domain/bridge-declarations/` 下加新 YAML——这是唯一的"该扩展"的触发条件
- 如果 `python framework/check.py .` 开始报 FAIL 而你没有改任何 YAML——有人在别处改了 schema.py 的字段名或约束 ID 格式。追查那个改动

# Anti-Patterns

- 不要"顺手"往 YAML 里加新约束——每条新约束必须是物理上可核查的，不是"我觉得应该有"
- 不要在实验跑不通时改 check.py 让它通过——check.py 是结构完整性嗅探器，绕过它等于关掉 smoke detector
- 不要把 YAML 当实验参数的配置中心——参数在 Python 里，YAML 是结构文档。混在一起会两头不讨好
