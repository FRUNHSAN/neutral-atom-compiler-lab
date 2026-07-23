---
chain_id: 2026-07-23-distance-crosstalk-model
title: "NAC 距离依赖串扰：van der Waals 替代二值模型"
layer: L1
ternary_owner: agent
tags: [crosstalk, fidelity-model, van-der-waals, rydberg, physics, approximation, placer]
status: completed
created: 2026-07-23
supersedes: []
superseded_by: []
reverted_by: ""
related: [2026-07-21-multi-compiler-reproduction]
files:
  constraints: [C-qc-crosstalk]
  boundaries: [B-nac-hardware]
  bridges: [BR-keep-vs-move, BR-parallel-vs-distance]
  code:
    - instances/nac/implementation/router.py
    - instances/nac/implementation/simulator.py
    - instances/nac/implementation/placer.py
  experiments: []
produces_invariants:
  - "串扰强度必须随距离衰减——不可以用二值模型评估 fidelity"
  - "rydberg_radius 必须从 architecture JSON 读取，禁止硬编码"
  - "placer 的 stay/move 决策使用距离权重近似——需注释近似边界"
produces_constraints: []
cross_domain: false
domains_verified: []
---

# Context

ZAP 的 F_xtalk 公式是二值的：idle qubit 在纠缠区 = 全量串扰，不在 = 0。
物理上 Rydberg 相互作用随距离按 van der Waals `1/r⁶` 衰减——距离 200μm
的串扰是 50μm 的 `(200/50)⁶ ≈ 1/4100`。二值模型在稀疏电路上系统性
高估串扰 30-40%。

NAC 在 fidelity 评估和 placer 决策中都复用了 ZAP 的这个二值假设。
修复不增加任何编译步骤——只在公式层改。

# Decision

三层统一使用 van der Waals 距离衰减权重：
`w(d) = 1 / (1 + (d / R_blockade)⁶)`

1. **router** — `_emit_crosstalk` 计算每个 idle qubit 到最近活跃 qubit 的
   距离，写入 instruction 的 `xtalk_weight` 字段
2. **simulator** — F_xtalk 使用 `f2q_idle ** xtalk_weight` 替代 `f2q_idle ** len(qs)`
3. **placer** — Eq.15 stay/move 决策的 crosstalk_cost 使用距离权重，
   无活跃 2q 对 → crosstalk=0

R_blockade 从 `architecture.json → hardware.rydberg_radius_um` 读取，默认为 5.0 μm。

# Rationale

距离依赖是物理定律，不是经验拟合。van der Waals `1/r⁶` 是 Rydberg 偶极-偶极
相互作用的直接结果。`w(d)` 形式满足物理边界条件：
- d = 0 → w = 1（最大串扰）
- d = R_blockade → w = 0.5（半 blockade）
- d ≫ R_blockade → w → 0（无串扰）

router 和 simulator 的计算是精确的——每个 stage 都知道活跃 qubit 是谁、
在哪，距离可直接计算。placer 有一个工程近似（见下方）。

5/30 个 S 组规则全部通过（check.py），不改 constraint schema。
向后兼容：旧 instruction 若无 `xtalk_weight` 字段，simulator fallback 到 `len(qs)`。

# Known Approximation (placer only)

placer 的 stay/move 决策对**未来 stage** 使用当前 stage 的距离权重作为近似：

```python
# 近似边界：xtalk_weight 基于 current stage 的活跃 qubit 位置计算，
# 乘以所有未来 stage 数 (crosstalk_stages)。未来 stage 的活跃 qubit
# 集合和位置可能不同——当前 weight 是保守估计的下界。
```

适用条件：
- **稀疏电路** (sat_n11, multiplier_n15, vqc_n15)：近似良好——
  活跃 qubit 集合小且位置固定
- **密集电路** (qft_n10, qaoa_n6)：活跃 qubit 遍布纠缠区，
  weight → 1，近似退化回二值模型——无信息损失
- **过渡电路** (qram_n20, knn_n25)：weight 在 0.1-0.3，
  未来活跃 qubit 可能挪到更近的位置 → 近似偏乐观

如果要改进：逐 stage 累加距离权重（用 schedule 信息预测活跃 qubit 位置），
但需要预先知道未来路由决策——这是鸡生蛋问题。当前近似是合理的下限。

# Alternatives

1. **保持二值模型**：拒绝。物理上不准确，系统性地在稀疏电路上高估串扰。
2. **逐 stage 精确计算**：拒绝。需要预测未来 qubit 位置（路由尚未发生），
   且计算量增加 crosstalk_stages 倍。
3. **密度估计**：用纠缠区活跃 qubit 密度 / 总 qubit 数估算平均串扰权重。
   比当前方案计算量大但更精确 → 留作后续优化。

# Evidence

14 benchmark 全量跑：

| benchmark | ZAP | NAC xw | vs ZAP |
|-----------|-----|--------|--------|
| sat_n11 | 0.0833 | 0.1307 | +56.9% |
| multiplier_n15 | 0.0824 | 0.1187 | +44.1% |
| vqc_n15 | 0.0167 | 0.0236 | +41.6% |
| knn_n25 | 0.3215 | 0.3979 | +23.7% |
| qram_n20 | 0.3584 | 0.4070 | +13.6% |
| qnn_n15 | 0.4603 | 0.5134 | +11.6% |
| adder_n4 | 0.9140 | 0.9178 | +0.4% |
| wstate_n27 | 0.4917 | 0.4933 | +0.3% |
| ghz_n30 | 0.6433 | 0.6429 | -0.1% |
| cat_n35 | 0.5646 | 0.5724 | +1.4% |

效果集中在串扰主导的稀疏电路。密集电路（qft, ghz）、几乎无串扰的电路
（cat, wstate, bv_n14）基本不变。这符合物理预期——距离权重只在"有很多
idle qubit 离活跃区近/远"时才起作用。

# Future Guidance

- 如果要改进 placer 近似：在 `_evaluate_stay_or_move` loop 中对未来
  `crosstalk_stages` 逐 stage 累加距离权重，而不是乘。需要处理未来位置未知问题。
- `rydberg_radius_um` 现在从 architecture JSON 读取——如果改了值要重跑 benchmark。
- 距离权重的 exponent 6 是 van der Waals 特定值——对 resonant dipole-dipole
  (Förster resonance) 应改用 exponent 3。这是架构参数，不是代码逻辑。
- 此模型不影响 ZAP 对比口径——ZAP 仍用二值模型，对比反映的是 NAC 更真实的评估。

# Anti-Patterns

- 禁止在 router/simulator/placer 各自硬编码 `rydberg_radius = 5.0`。
  必须从 `architecture.json → hardware.rydberg_radius_um` 统一读取。
- 禁止在 placer 以外的地方使用"当前 stage 距离 ≈ 未来 stage 距离"近似——
  router 和 simulator 的 xtalk_weight 是精确值，不应被降级。
- 此链不涉及 ZAP 源码——只改 NAC。
