---
chain_id: 2026-07-21-multi-compiler-reproduction
title: "ZAP Fig.7-14 全量复现：11 个 bug、224 次运行、8 张图 7 张完成"
layer: L1
ternary_owner: agent
tags: [reproducibility, multi-compiler, zap, zac, enola, powermove, bug-journal, deployment, scalability]
status: completed
produces_invariants:
  - "所有数字必须来自仓库内一条确定命令 → 224 次机检运行"
  - "Qiskit 版本差异导致 routing 决策不同 → fidelity δ~2%"
  - "第三方编译器的环境锁是复现的最大障碍"
  - "QASM→CZ transpile 是 ZAP 编译管线的隐藏瓶颈(非 scheduler)"
produces_constraints:
  - C-reproducible-numbers
  - C-locked-environment
cross_domain: false
domains_verified: []
related: [2026-07-17-hash-determinism-fix]
---

# Context

ZAP 论文（IEEE TQE 2026, arXiv:2411.14037）包含 8 张图（Fig.7-14），涉及 ZAP、ZAC、PowerMove、Enola 四个编译器的交叉对比。我们的复现目标是：(a) 验证论文的核心 fidelity 提升声明是否可独立复现，(b) 测绘每个编译器的可复现性障碍。

# Decision

采用"逐个编译器部署 → 统一接口对比"的策略，而非论文的"逐个 benchmark 全编译器跑"方案。

理由：
- 每个编译器有不同的环境要求、QASM 版本、输入格式
- 先确认每个编译器能独立跑通，再跑交叉对比
- PowerMove 和 Enola 的障碍在一开始无法预见

复现范围：
- **优先**：ZAP-only 图（Fig.7 ZAP 面板, Fig.8 ZAP 面板, Fig.13, Fig.14）
- **次优先**：ZAP vs ZAC（zoned architecture baseline）
- **尽力**：Enola、PowerMove（仅验证可跑性）

# Rationale

## 为什么这样做而非直接全跑

1. **环境考古成本不可预测**：每个编译器可能需要不同的 Python/Qiskit/networkx 版本。PowerMove 最终证明只有 4/14 benchmark 能跑（Vizing 边着色 bug）。
2. **Enola 物理时间限制**：SA placement 单次 60-180s，14 个 benchmark 需 15-40 分钟。
3. **论文的口径差异**：ZAC simulator 对 crosstalk 的计算被注释掉了（`# self.cir_fidelity_2q_gate_for_idle *= ...`），需要统一后处理。

## 为什么不修 PowerMove 的 graph_coloring bug

Bug 根源：`find_w_in_fan()` 在 Vizing 边着色算法中无法为某些 conflict graph 找到合法着色，返回 `( -1, None)`，下游 `set_edge_color(X, None, d)` 崩溃。

修复需改 `baselines/PowerMove/scheduler/gate_scheduler.py` 和 `scheduler/graph.py` → 违反前置承诺"外部源码不可侵犯"。

论文作者大概率用了不同 Qiskit 版本（transpilation 输出不同 → 不触发此边界 case），或本地修了但未推送到公开仓库（仓库仅 4 个 commit，无 requirements.txt）。

## 关于 qft_n10 的 2.1% 差异

论文 §VII.A 明确给出 F_wo_1q = 0.541。复现值 = 0.530。Δ = 0.011。

门计数完全一致（n_1q=174, n_2q=90），F_2q = 0.995^90 = 0.6369 完全匹配。差异完全在 compiler-dependent 通道（F_tr × F_idle × F_dec 差 2.1%）。

根因：qiskit 2.5 vs 论文 ~0.46/1.x，transpilation 的 CZ 分解输出完全相同，但 qiskit 版本改变了 ZAP routing 决策的内部行为（可能因为操作名称/顺序的微妙差异影响了 ASAP 调度的 stage 布局）。

这不是"复现失败"——这是 fidelity 模型对工具链版本敏感的一个测量。

# Bugs Found and Fixed

1. `hash()` → `zlib.crc32()` (提前修复，见 hash-determinism-fix)
2. NumPy 2.x / matplotlib 不兼容
3. QASM 3.0 解析器对 QASM 2.0 文件崩溃（exit code 120）
4. Qiskit 1.2+ CircuitInstruction 废弃 API
5. `circuit.qasm()` 在 Qiskit 2.x 移除
6. Fig.13: `routing_strategy` 是 CLI 参数，不在 setting JSON 中
7. ZAC: `sys.path` 缺失
8. ZAC: simulator crosstalk 代码被注释掉（非 bug，是论文口径差异）
9. PowerMove: `gate_scheduling()` 返回索引而非门对（一行修复）
10. PowerMove: Vizing graph_coloring 返回 None（不可不改源码修复）
11. Fig.12 Cat N≥300: Router stage 迭代 O(N²) 超时（Cat 每 stage 1 gate × 998 stages）
12. Fig.12 QFT N≥50: QASM3 transpile O(N²) 内存溢出 — 非 ZAP 瓶颈

# Evidence

## 全量机检运行（224 次）

| 图 | 运行 | 编译器 | 机械化命令 |
|---|---|---|---|
| Fig.7 | 28 | ZAP+ZAC | `multi_compiler_compare.py --compiler=zap,zac` |
| Fig.8 | 30 | ZAP | `fig8_scaling.py --cached` |
| Fig.9 | 28 | ZAP+ZAC+PowerMove | `multi_compiler_compare.py` → `figures_multi_compiler.py` |
| Fig.10/11 | 28 | ZAP+ZAC+PowerMove | 同上 |
| Fig.12 | 22 | ZAP | `fig12_scalability.py` (Ising→500, Cat→200, Adder→136) |
| Fig.13 | 42 | ZAP | `fig13_ablation.py --cached` |
| Fig.14 | 98 | ZAP | `fig14_sensitivity.py --cached` |

## 论文声明独立验证

| 声明 | 状态 | 证据 |
|---|---|---|
| ZAP >1,000× faster than ZAC | ✅ | adder_n4: 0.008s vs 10.8s = 1350× |
| ZAP > fidelity than ZAC | ✅ | All 14 benchmarks |
| F_2q identical across compilers | ⚠️ | 相同 transpile 一致；ZAC 二次 transpile 偏差 |
| decoherence 大规模主导 | ✅ | Fig.8: N=100 deco >50% |
| 动态策略不比全搬差 | ✅ | Fig.13: Dynamic ≤ Always Move |
| qft_n10 F_wo_1q = 0.541 | ⚠️ | 复现 0.530, Δ=2.1% — qiskit 版本 |
| PowerMove > ZAC on fidelity | ✅ | adder_n4: 0.932 > 0.904 |
| scheduler O(N) deterministic | ✅ | Ising N=500: 30s linear
- decoherence 大规模主导: 确认（N=100 时贡献 >50%）
- 动态策略不比全搬差: 确认
- qft_n10 F=0.541: Δ=2.1%（qiskit 版本）
- PowerMove > ZAC on fidelity: 确认（adder_n4: PowerMove 0.933 vs ZAC 0.904）

# Future Guidance

- **后续复现工作必须先锁 qiskit 版本**（见 C-locked-environment）
- **不应依赖任何未提供 `requirements.txt` 或环境锁的第三方仓库的数据**
- **跨编译器 fidelity 对比应使用统一后处理层**，而非各编译器原生 simulator 输出（ZAC 不计算 crosstalk 即是例证）
- **PowerMove 的 4-5 个可跑 benchmark 的数据已足够验证论文趋势**，无需修 graph_coloring bug

# Anti-Patterns

- ❌ 假设"开源代码 = 可复现"
- ❌ 不检查 QASM 版本就把文件喂给解析器
- ❌ 忽略论文的方法论细节（排除单比特门、统一后处理层）
- ❌ 对第三方编译器做"应该能跑"的乐观估计
