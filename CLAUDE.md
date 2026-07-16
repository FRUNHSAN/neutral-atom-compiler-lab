# neutral-atom-compiler-lab — 中性原子量子编译器分析

> 约束式工程框架 × 中性原子量子编译器。
> 以 ZAP (IEEE TQE 2026) 为第一个完整分析对象。

## 启动序列

```
1. pip install pyyaml
2. python framework/check.py .                ← 约束一致性检查（0 FAIL = 可以开工）
3. python experiments/strategy_compare.py     ← 硬阈值 vs AL 软决策
4. python experiments/bridge_swap.py          ← 六桥 swap (synthetic)
5. python experiments/bridge_swap.py --zap-path <path>  ← 六桥 swap (live ZAP)
```

## 项目目的

1. **分析层**：测绘 ZAP 编译器单遍确定性范式的适用边界
2. **方法层**：验证约束式工程框架在真实编译器上的分析能力
3. **产出层**：为 BAQIS "量子青年人才储备计划"申请提供可核查的技术基础

## 约束式工程三层

### Constraint（约束层 — `constraints/C-qc-*.yaml`）
10 条约束定义"应该是什么"——物理定律、formal 数学陈述、rigidity（hard/soft/objective）、stage（discovery→translation→reduced→implemented）、G(C) 跨域可迁移性。

### Boundary（边界层 — `boundaries/B-*.yaml`）
2 条边界定义"错了扣多少分"——cost_terms（代价公式+参数）、cost_groups（聚合组）、assumptions（硬件假设）、discretization_gap（已知的离散化误差）。

B-zap-hardware：zone 架构，L_stay = [L_xtalk]，L_move = [L_tr, L_dec]
B-enola-hardware：单区架构，hardware_fixed / compiler_optimizable 分离

### Bridge（桥接层 — `bridges/BR-*.yaml`）
2 座桥定义"张力怎么解决"——source↔target（约束或 cost_group）、resolve_fn（compare/weighted/solver）、coupled（是否联合优化）。

BR-keep-vs-move：coupled=true → 外部求解器（SolverAdapter）
BR-parallel-vs-distance：coupled=false → 加权比较

### Framework（`framework/`）
- schema.py：Constraint / Boundary / Bridge 数据模型
- solver_adapter.py：SolverAdapter ABC + Solution
- io.py：YAML 加载 + 三层注册表构建
- check.py：30 条一致性检查规则（F/B/BR/S/I 五组）
- tags.yaml：受控领域词汇表

## 六桥

ZAP 的 6 个决策点：
1. **keep-vs-move** (BR-keep-vs-move)：空闲比特留在纠缠区还是搬回存储区 — 唯一高敏感性参数
2. **λ_par** (BR-parallel-vs-distance)：并行化 vs 搬运距离的权衡权重
3. **parking** (BR-parking-displacement)：搬回存储区时的坑位选择策略
4. **ASAP** (BR-asap-strategy)：调度策略（separate / joint）
5. **qubit priority** (BR-qubit-priority)：哪几个比特优先占纠缠区槽位
6. **idle_cost_alpha** (BR-idle-cost-alpha)：闲置代价和搬运代价的换算系数

## Fidelity 模型 (Eq. 4)

统一的跨编译器 fidelity 公式：
F_total = F_1q × F_2q × F_xtalk × F_transfer × F_coherence

## 关键约束

- 不改 ZAP 源码——所有决策点替换通过 monkey-patch 或架构 JSON 注入
- 同一个 fidelity 公式跨编译器对比——避免口径差异
- 所有实验可复现——脚本参数化
- constraint 管"什么是对/错"，boundary 管"错了扣多少分"，implementation 管"怎么做到"——三者不混

## 相关项目

- ZAP：https://github.com/BAQIS-Quantum/neutral-atom-compilation（MIT 许可证）
- Enola：https://github.com/UCLA-VAST/Enola
- ZAC：https://github.com/UCLA-VAST/ZAC
- PowerMove：https://github.com/Scarlett0815/PowerMove
- 母仓库：constraint-engineering-lab（D:/constraint-engineering-lab/）
