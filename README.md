# neutral-atom-compiler-lab

> 中性原子量子编译器分析——约束式工程框架 × ZAP 范式边界测绘。
> 面向北京量子信息科学研究院 2026 年"量子青年人才储备计划"，目标导师：胡孟军。

## 一句话

不修改 ZAP（IEEE TQE 2026）源码，用 monkey-patch 替换全部 6 个决策点，在 3 类电路上完成基准对比；用同一 fidelity 公式交叉验证 Enola / ZAC / ZAP 三个编译器（11/11 PASS）。下一步：把 ZAP 的固定参数变成硬件和电路自适应参数，测绘单遍确定性编译范式的适用边界。

**整个项目由约束式工程框架组织——10 条约束 + 2 条边界 + 2 座桥 + 30 条自动化一致性检查规则。**

---

## 约束式工程三层结构

```
constraints/ (10 条 YAML)     ← "应该是什么" — 物理定律, formal, rigidity, stage
    │
    └── boundaries/ (2 条 YAML) ← "错了扣多少分" — cost_terms, cost_groups, assumptions
           │
           └── bridges/ (2 条 YAML) ← "张力怎么解决" — source↔target, resolve_fn, coupled
                  │
                  ├── src/nac_lab/adapter.py ← 可插拔求解器 (SolverAdapter)
                  │       └── hard_threshold: ZAP Eq.15 逐比特独立决策
                  │       └── al_soft: 增广拉格朗日联合优化 (0 slot 违规)
                  │
                  └── experiments/ ← 六桥 swap + 三编译器交叉验证
```

**约束注册**：ZAP 1932 行源码 → 10 条可形式化约束（86% 转化率），求解策略（1005 行）不转化——它们属于 implementation，不是 constraint。

---

## 做了什么（12 commits，已完成）

### 六桥基准测试

| Bridge | ZAP 默认 | 替代方案 | Δ | 敏感性 |
|--------|---------|---------|------|--------|
| BR-keep-vs-move | lookahead 硬阈值 | AL 软决策 | 0 (此规模) | **高** |
| BR-parallel-vs-distance | λ=1000 | 电路自适应 | 0 | 无 |
| BR-parking-displacement | 1 site | 5 sites | <0 (更差) | 弱 |
| BR-asap-strategy | separate | joint | 0 | 无 |
| BR-qubit-priority | 1/(l+1) | reuse-aware | 0 | 无 |
| BR-idle-cost-alpha | α=1.0 | α∈[0.5,5.0] | α=5 掉 | 中 |

**核心发现：6 个决策点中只有 keep-vs-move 是高敏感性参数。** 九分钟跑完六桥——快速排除五个无效方向。

### 三编译器 Fidelity 交叉验证

同一公式（Eq.4），验证三个编译器内置模拟器：

| 编译器 | 验证结果 | 关键发现 |
|--------|---------|---------|
| Enola | 5/5 PASS | 无 zone → crosstalk=0.975 |
| ZAC | 6/6 PASS | zone 架构 → crosstalk=1.0（消除） |
| ZAP | 内置一致性 | lookahead / always_move / always_stay |

### 约束一致性检查

```
$ python framework/check.py .
  PASS: 0 FAIL / 0 WARN / 7 FYI
```
30 条规则自动验证：ID 格式、stage 合法性、derives_from DAG 无环、boundary 链接完整、bridge source/target 有效、coupled bridge resolve_fn=solver……

---

## 项目结构

```
neutral-atom-compiler-lab/
├── README.md                        ← 你在这里
├── CLAUDE.md
├── pyproject.toml
│
├── framework/                       ← 约束式工程框架（轻量，自包含）
│   ├── schema.py                    ← Constraint / Boundary / Bridge 数据模型
│   ├── solver_adapter.py            ← SolverAdapter ABC + Solution
│   ├── io.py                        ← YAML 加载 + 三层注册表
│   ├── check.py                     ← 30 条一致性检查规则
│   └── tags.yaml                    ← 受控领域词汇表
│
├── constraints/                     ← 约束层（10 条 YAML）
│   ├── C-qc-connectivity.yaml       ← 里德堡阻塞半径
│   ├── C-qc-crosstalk.yaml          ← 串扰抑制
│   ├── C-qc-fidelity.yaml           ← 五通道保真度
│   ├── C-qc-transport.yaml          ← 原子搬运
│   ├── C-qc-decoherence.yaml        ← 退相干
│   ├── C-qc-aod-routing.yaml        ← AOD 行列路由
│   ├── C-qc-bandwidth.yaml          ← 并行搬运带宽
│   ├── C-qc-slot-assignment.yaml    ← 坑位分配
│   ├── C-qc-parking.yaml            ← 搬运轨迹不重叠
│   └── C-qc-depth.yaml              ← 电路深度最小化
│
├── boundaries/                      ← 边界层（2 条 YAML）
│   ├── B-zap-hardware.yaml          ← ZAP zone 架构 cost model
│   └── B-enola-hardware.yaml        ← Enola 单区 cost model
│
├── bridges/                         ← 桥接层（2 条 YAML）
│   ├── BR-keep-vs-move.yaml         ← coupled=true (联合优化)
│   └── BR-parallel-vs-distance.yaml ← coupled=false (加权比较)
│
├── src/nac_lab/                     ← 核心库
│   ├── fidelity.py                  ← Eq.4 五通道 fidelity 模型
│   ├── adapter.py                   ← ZAP 域适配器 (继承 SolverAdapter)
│   └── bridges.py                   ← 六桥注册表 + 敏感性分类
│
├── baselines/                      ← 第三方编译器源码（gitignored）
│   ├── neutral-atom-compilation/   ← ZAP (MIT 许可证, IEEE TQE 2026)
│   ├── Enola/                      ← Enola (UCLA-VAST)
│   └── ZAC/                        ← ZAC (UCLA-VAST, HPCA 2025)
│
├── experiments/                     ← 四个独立实验脚本
│   ├── bridge_swap.py               ← 完整六桥 swap
│   ├── cross_validate.py            ← 三编译器 fidelity 交叉验证
│   ├── strategy_compare.py          ← 硬阈值 vs AL 软决策
│   └── lambda_par_swap.py           ← λ_par 参数扫描
│
├── docs/
│   ├── RESEARCH.md                  ← 3 个月研究计划书
│   ├── SUMMARY.md                   ← 已完成工作总结
│   └── reading/                     ← 文献阅读笔记
│
└── results/                         ← 实验输出
```

---

## 3 个月研究计划

| 周 | 实验 | 文献 | 里程碑 |
|----|------|------|--------|
| 1–2 | WP0 benchmark 扩展到不规则电路 | Tier 1 精读（Enola/ZAC/PowerMove） | D1 扩展对比表 |
| 3–6 | WP1 四维灵敏度扫描 → 危险区 | Tier 2 谱系 + 硬件锚点 | D2 危险区刻画 |
| 7–10 | WP2 zone sizing 电路自适应 | Tier 3 前沿（BRIDGE 核查优先） | D3 zone 曲线族 |
| 11–12 | WP3 综合写作 | 补漏整理 | D4 技术报告草稿 |

---

## 快速开始

```bash
pip install pyyaml
python framework/check.py .                         # 约束一致性检查
python experiments/strategy_compare.py              # 硬阈值 vs AL 软决策
python experiments/bridge_swap.py                   # 六桥 swap (synthetic)
python experiments/bridge_swap.py --benchmark qft_n10  # 六桥 swap (live ZAP — 自动使用 baselines/)
```

---

## 为什么选中性原子编译器

1. **双维度耦合**（空间搬运 + 时序调度）→ 约束复杂度恰好够穷举，恰好逼出框架的所有桥类型
2. **硬件参数快速演化**（2022 年首展相干搬运，至今参数每年在变）→ boundary 层被真实考验
3. **6+ 个竞争编译器** → 交叉验证有真活可干，`equivalence` 桥有数据支撑
4. **范式窗口**（DT / BRIDGE 2026 年正在从硬件层挑战搬运范式）→ `substitutes` 语义被压到极限

换个平台——超导约束太简单，离子阱是一次性桥，光子映射成本太高——都构不成完整验证集。

---

## 联系方式

- 作者：[你的名字]，大三本科生
- 目标：北京量子信息科学研究院 胡孟军 课题组
- 项目性质："量子青年人才储备计划"申请材料的一部分
