# neutral-atom-compiler-lab — 中性原子量子编译器分析

> 约束式工程框架 × 中性原子量子编译器。
> 以 ZAP (IEEE TQE 2026) 为第一个完整分析对象。

## 启动序列

```
1. pip install pyyaml
2. python framework/check.py .                ← 约束一致性检查 + .stale.json 时间序列归档（0 FAIL = 可以开工）
3. python experiments/strategy_compare.py     ← 硬阈值 vs AL 软决策
4. python experiments/bridge_swap.py          ← 六桥 swap (synthetic)
5. python experiments/bridge_swap.py --zap-path <path>  ← 六桥 swap (live ZAP)
```

## 框架架构速查

> 四层 + 桥三维 + 尺子等效 + 参数分工 + 约束生命周期。施工图见 `CLAUDE copy.md`（母仓库框架完整版）。

### 四层

```
framework/         元层 — 域无关的元语言（schema / check / solver_adapter / io）
domain/            第1层 — 所有实例共享：约束 + 公式 + 张力声明（BD-xxx）
instance-space/    第2层 — 实例们共存的环境：尺子 + 等效声明
instances/         第3层 — 每个实例私有的选择：边界 + 决策桥（BR-xxx）
```

### 桥的三维：type × mode × layer

```
type (7):  connect / merge / reuse / tension / degrade / priority / supersede
mode (2):  independent（逐元素函数） / coupled（优化问题 → SolverAdapter）
layer (2): declaration（BD-xxx, 域级, 不含解法） / instance（BR-xxx, 含解法+参数）

端点九种组合，三种成立: D↔D / I↔I 同实例 / S↔S（尺子比较，不用桥）
```

### 尺子与等效声明

尺子是实例空间的**存在条件**——没尺子 = 场景描述，不是实例空间。尺子三元组：`metric`（量什么）+ `formula_ref`（怎么量）+ `tolerance`（equivalent 阈值 + notable 阈值）。

等效声明五个字段：`(approaches, constraint, ruler, conditions, via)`。全引用，check.py 可机械化验证。等效 = 用同一把尺子量，|delta| < ruler.tolerance.equivalent。

### 参数三层分工

```
domain/constraint.formal:  "dist ≤ R_blockade"        ← 关系结构（物理）
instance-space/protocol:   R_blockade: 4.3            ← 共享测量值
instances/boundary:        f_2q_idle = 1-(1-f2)/2     ← 私有近似
```

规则：`formal` 只写关系不写数值。数值属于 instance-space 或 instances。

### 约束生命周期（四阶段）

| 阶段 | `stage` | 产出 | 退出条件 |
|------|---------|------|---------|
| 发现 | `discovery` | constraint.yaml (id+name) | 人判断收敛 |
| 翻译 | `translation` | + formal + derives_from | 无残渣 |
| 简化 | `reduced` | boundary.yaml | 再压丢信息 |
| 实现 | `implemented` | implementations/*.py | 测试通过 |

`stage` 只能相邻跳转（S1 检查）。跳过中间阶段 → FAIL。

### 机械化边界

结构检查（全机械化 — check.py 30 条规则）：引用存在 / 字段非空 / DAG 无环 / tolerance 自洽 / 等效声明四元组不重复。语义检查（不可机械化）：|delta| < tolerance → 跑 benchmark。等效是否正确 → 人判断。

---

## 项目目的

1. **分析层**：测绘 ZAP 编译器单遍确定性范式的适用边界
2. **方法层**：验证约束式工程框架在真实编译器上的分析能力
3. **产出层**：为 BAQIS "量子青年人才储备计划"申请提供可核查的技术基础

## 本项目的约束/边界/桥实例

### Constraint（`domain/constraints/C-qc-*.yaml`）
10 条约束定义"应该是什么"——formal 数学陈述、rigidity（hard/soft/objective）、stage、G(C) 跨域可迁移性。

### Boundary（`instances/*/boundaries/B-*.yaml`）
2 条边界定义"错了扣多少分"——cost_terms、cost_groups、assumptions、discretization_gap。
- B-zap-hardware：zone 架构，L_stay=[L_xtalk]，L_move=[L_tr, L_dec]
- B-enola-hardware：单区架构，hardware_fixed / compiler_optimizable 分离

### Bridge（`instances/*/bridges/BR-*.yaml`）
2 座桥定义"张力怎么解决"——source↔target、resolve_fn（compare/weighted/solver）、coupled。
- BR-keep-vs-move：coupled=true → SolverAdapter
- BR-parallel-vs-distance：coupled=false → 加权比较

### Framework（`framework/`）
- schema.py：Constraint / Boundary / Bridge 数据模型
- solver_adapter.py：SolverAdapter ABC + Solution
- io.py：YAML 加载 + 三层注册表构建
- check.py：30 条一致性检查规则（F/B/BD/BR/IS/D/S 组 + S10 链完整性）
- stale_snapshot.py：.stale.json 时间序列归档
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

## AI 协作者约束协议（精简版）

> 完整版见 `docs/papers/constraint-engineering-theory/16-AI协作者约束协议.md`
> 理论基座见 `docs/papers/constraint-engineering-theory/31-三元架构：人-AI-框架协作的形式化.md`
>
> AI 是本框架的**语义推理引擎**（非工具）。以下协议是 AI 的行为约束——违反协议 = 违反铁律。

### 启动自检（每次会话必须）

AI 首次响应必须输出：
```
[约束协议加载确认]
HEAD: <git rev-parse --short HEAD>
Protocol 0-7: loaded
Chains: N public + M private（读 .ai_reasoning/index.yaml + index_private.yaml）
文档路径: docs/papers/constraint-engineering-theory/
首次会话: 请读 docs/papers/constraint-engineering-theory/34-推理链制作方法.md + .ai_reasoning/chains/_TEMPLATE.md
```

### Protocol 0 — 文档优先
决策前检索 `docs/papers/constraint-engineering-theory/` 中的相关约束。
**违规**：建议未引用文档 ID → WARNING。

### Protocol 1 — 来源验证
新规则标注 `[来源: 公理推导/经验推测] [置信度: HIGH/MEDIUM/LOW]`。
**违规**：无法提供来源 → 禁止建议。

### Protocol 2 — 反模式扫描
每次代码审查逐项扫描 `12-反模式目录.md` 的 10 项。
**违规**：审查报告缺反模式扫描 → 补充。

### Protocol 3 — 跨域一致性
单域修改约束 → 检查另外两个域是否需要同步修改。
输出 `CROSS_DOMAIN_CONSISTENCY_CHECK`。

### Protocol 4 — 铁律不可侵犯
禁止修改 7 条铁律的数学形式。参数可调，形式不可改。
**违规**：ERROR → 人工二次确认。

### Protocol 5 — 遗忘预防
代码偏离文档原则 → 指出偏离 + 提供选项：(a) 回滚代码 (b) 更新文档。
连续 3 次同一约束被绕过 → 触发 Protocol 7。

### Protocol 6 — 冲突升级
- L1（局部冲突）：按公理优先级裁决（铁律 > 方法论推导 > 域参数）
- L2（文档-现实漂移）：参数差异>2× 或形式非等价变换 → DRIFT_ALERT + 等待 H 裁决
- L3（铁律悖论）：两条铁律逻辑互斥 → **立即停止所有工程建议**，仅输出 IRON_LAW_PARADOX

### Protocol 7 — 约束稳态维护
约束触发率<0.1 → STALE。场景不存在 → DEPRECATED。重叠≥80% → MERGE_CANDIDATE。
AI **仅有提议权**。H 拥有裁决权。
废弃约束 → `archive/deprecated/`，保留完整元数据。**禁止物理删除。**

### Protocol 8 — 约束与求解器分离
`formal` 只写关系（`dist ≤ R`），不写数值（`R=4.3`）。
数值进 `instance-space/protocol` 或 `instances/boundary`。求解器进 `implementations/`，不进 YAML。
**违规**：formal 含参数数值 → `check.py` F6 报 WARN。
**违规**：求解逻辑出现在约束/边界/桥 YAML → ERROR，建议新建 `implementations/`。

### 前置承诺 — 外部源码不可侵犯

**生效条件**：项目根目录存在 `baselines/` 目录时自动激活。不存在则本条休眠——不报、不拦、不加载。

激活后：不改 `baselines/` 下的任何第三方源码。所有决策点替换通过 monkey-patch 或架构 JSON 注入。新增功能 → `instances/<name>/adapter.py`。
**违规**：直接修改 baselines/ 源码 → ERROR，必须回滚。实验可复现性取决于此。

> 复制 CLAUDE.md 到新项目时：如果新项目有 baselines/，本条自动生效。如果没有，整条可删除或保留休眠。

### 分层检索优先级

| 层 | 何时加载 | 内容 |
|----|---------|------|
| L0 | 每次会话必加载 | CLAUDE.md + 当次任务相关域速查（13/14/15 之一） + 推理链制作方法.md（首会话或新 AI 协作者加入时） |
| L1 | 决策前按需 | 涉及的约束/边界/桥 YAML + `.ai_reasoning/chains/` 中相关链 |
| L2 | 冲突时 | Doc 12（反模式）+ Doc 10（实践方法论） |
| L3 | 理论争议时 | Doc 29（结构论）+ Doc 31（三元架构）+ Doc 18（公理） |

检索后输出 `[RETRIEVED: doc_id, ...]` 供 H 追溯。

### 推理链速查

> 推理链记录"为什么不那样做"。详见 `docs/papers/constraint-engineering-theory/34-推理链制作方法.md`。

```
.ai_reasoning/
├── chains/ + index.yaml          ← 公开链（git 追踪）
└── chains_private/ + index_private.yaml  ← 私有链（仅本地）

改代码前:  读两个 index → grep tags → 读链的 Future Guidance + Anti-Patterns
改代码后:  该写链吗？
            ├─ ≥2方案选择 / 不显而易见的约束 / 设计缺陷修复 / 影响≥3模块
            │   → 写。公开(chains/)还是私有(chains_private/)？
            │     复制 _TEMPLATE.md → context+decision+rationale → 更新 index
            │     代码加 @chain: / @invariant: 标记
            │     ⚠ 公开链的 related 不能引用私有链 ID（S10(f)）
            └─ typo / 单行bug / 纯重构 → 不写
跨链移动:  私→公: 移文件 + 更两个 index + 查 related。详见方法论 §十一
验证:      python framework/check.py .  →  S10 自动检查链完整性
```
