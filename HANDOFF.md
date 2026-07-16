# 工作进度报告 — 中性原子量子编译器分析

> 写给接手这个项目的下一个 AI / 人类。
> 最后更新：2026-07-16

---

## 零、这个项目是什么

对 ZAP 编译器（IEEE TQE 2026，胡孟军团队）做**决策点分析 + 范式边界测绘**。不修改 ZAP 源码，用 monkey-patch 替换它的 6 个决策点，用约束式工程框架组织整个分析流程。

**目标申请**：北京量子信息科学研究院 2026 年"量子青年人才储备计划"，目标导师胡孟军。

---

## 一、已完成（5 个 git commit）

| commit | 内容 |
|--------|------|
| `ec21c28` | 项目初始化：fidelity 模型 + 六桥注册表 + 4 个实验脚本 |
| `9e709aa` | 约束式工程框架集成：10 条约束 YAML + 2 条边界 + 2 座桥 + check.py (30 条规则) |
| `075b6b9` | 集成第三方编译器源码 (ZAP + Enola + ZAC in `baselines/`，gitignored) |
| `46d990f` | docs/papers/ 文件夹 (gitignored，放论文 PDF) |
| `14e850f` | **四层架构重构** — domain / instance-space / instances + 桥的三维 (type×mode×layer) |

### 核心产出

- **六桥基准测试**：ZAP 的 6 个决策点全部被 monkey-patch 替换，在 QFT/Ising/GHZ 三类电路上跑完对比。结论：只有 `keep-vs-move` 是高敏感性参数，其余 5 个已达 fidelity 平台期。
- **三编译器交叉验证**：用同一 fidelity 公式 (Eq.4) 验证 Enola (5/5 PASS)、ZAC (6/6 PASS)、ZAP (内置一致性)。
- **约束式工程四层架构**：domain (约束) → instance-space (协议+尺子) → instances (编译器私有选择)，由 `framework/check.py` 自动验证一致性 (0 FAIL)。

---

## 二、快速启动（新手 30 秒）

```bash
cd d:/neutral-atom-compiler-lab

# 1. 安装依赖
pip install pyyaml

# 2. 验证框架自洽
python framework/check.py .
# 预期: PASS: 0 FAIL / 0 WARN / 11 FYI

# 3. 跑核心实验 (无需 ZAP 源码 — synthetic 模式)
python experiments/strategy_compare.py

# 4. 跑六桥 swap (synthetic 模式)
python experiments/bridge_swap.py

# 5. 跑 λ_par 参数扫描 (synthetic 模式)
python experiments/lambda_par_swap.py

# 6. 跑 live ZAP (需要 baselines/ 里的 ZAP 源码)
python experiments/bridge_swap.py --benchmark qft_n10
```

---

## 三、项目结构（改造后）

```
neutral-atom-compiler-lab/
│
├── framework/                  ← 元层：域无关的元语言
│   ├── schema.py               ← Constraint / Boundary / Bridge 数据模型
│   │                              Bridge 三维: type(7)×mode(independent|coupled)×layer(declaration|instance)
│   ├── solver_adapter.py       ← SolverAdapter ABC + Solution (可插拔求解器接口)
│   ├── io.py                   ← YAML 加载 + 注册表构建
│   ├── check.py                ← 14 条规则, F/BD/B/BR/IS/D/S/I 八组
│   └── tags.yaml               ← 受控领域词汇表
│
├── domain/                     ← 第1层：所有编译器共享
│   ├── constraints/            ← 10 条约束 (C-qc-*.yaml)
│   │   └── 每条: id, formal, rigidity, G(C), derives_from, domain_tags
│   │       formal 只写关系 (dist ≤ R), 不写数值 (R=4.3) — 数值在 instance-space
│   ├── formulas/               ← 域级公式 (结构, 不是参数)
│   │   └── fidelity.py         ← Eq.4 五通道乘积: ErrorCounts + FidelityBreakdown + compute_fidelity()
│   └── bridge-declarations/    ← 域级桥声明 (空 — Rule of Three: 三个实例面对同一对张力才建)
│
├── instance-space/             ← 第2层：实例们共同生活的环境
│   └── tqe-benchmark/          ← 第一个实例空间 (ZAP IEEE TQE 2026 benchmark 套件)
│       ├── protocol.yaml       ← 三要素: conventions(参数+规则) + ruler(尺子) + benchmarks
│       │   └── ruler: metric + formula_ref + tolerance(equivalent=0.001, notable=0.01)
│       │       无尺子 = 不是实例空间, 只是场景描述
│       └── declarations/       ← 等效声明 — 属于 (实例, 空间) 配对
│           └── BV-qft_n10.yaml ← 四元组: (approaches, constraint, ruler, conditions)
│
├── instances/                  ← 第3层：每个编译器私有的选择
│   ├── ZAP/
│   │   ├── boundaries/         ← B-zap-hardware.yaml — cost_terms + cost_groups
│   │   ├── bridges/            ← 2 座实例桥 (mode+layer+declares 字段)
│   │   │   ├── BR-keep-vs-move.yaml     ← type:tension, mode:coupled, layer:instance
│   │   │   └── BR-parallel-vs-distance.yaml  ← type:tension, mode:independent
│   │   └── adapter.py          ← ZAPKeepVsMoveAdapter — 实现 SolverAdapter
│   │       ├── hard_threshold: ZAP Eq.15 逐比特独立决策
│   │       └── al_soft: 增广拉格朗日联合优化 (slot 容量约束)
│   ├── Enola/
│   │   └── boundaries/         ← B-enola-hardware.yaml (单区架构, 无 zone)
│   └── ZAC/                    ← (待补: 缺 boundary + bridge)
│
├── experiments/                ← 四个独立实验脚本
│   ├── strategy_compare.py     ← 硬阈值 vs AL 软决策 (核心实验)
│   ├── bridge_swap.py          ← 完整六桥 swap (synthetic 模式 + live ZAP 模式)
│   ├── cross_validate.py       ← 三编译器 fidelity 交叉验证
│   └── lambda_par_swap.py      ← λ_par 参数扫描
│
├── src/nac_lab/                ← 核心库 (保留 bridges.py 六桥注册表 + fidelity 旧版)
│
├── baselines/                  ← 第三方编译器源码 (gitignored, 75MB)
│   ├── neutral-atom-compilation/  ← ZAP (MIT 许可证, IEEE TQE 2026)
│   ├── Enola/                     ← Enola (UCLA-VAST)
│   └── ZAC/                       ← ZAC (UCLA-VAST, HPCA 2025)
│
├── docs/
│   ├── RESEARCH.md             ← 3 个月研究计划书 (4 个工作包)
│   ├── SUMMARY.md              ← 已完成工作总结
│   ├── papers/                 ← 论文 PDF (gitignored)
│   └── reading/                ← 文献阅读笔记
│
└── results/                    ← 实验输出
```

---

## 四、引用链 — check.py 可全机械化验证

```
约束 → 约束:          C-qc-fidelity derives_from C-qc-crosstalk              [F3 验证]
边界 → 约束:          B-zap-hardware.constraint → C-qc-fidelity               [B1 验证]
实例桥 → cost_group:  BR-keep-vs-move.source → L_stay                         [BR1 验证]
实例桥 → 声明桥:      BR-keep-vs-move.declares → BD-crosstalk-vs-transport    [BR4 验证]
等效声明 → 尺子:      BV-qft_n10.ruler → protocol.yaml                        [D1 验证]
等效声明 → 约束:      BV-qft_n10.constraint → C-qc-crosstalk                  [D1 验证]
等效声明 → 实例+桥:   approaches[].instance → ZAP, approaches[].bridge → BR-* [D1 验证]
实例空间 → 尺子:      protocol.ruler 存在 → 这是实例空间, 不是场景描述          [IS1 验证]
尺子自洽:             tolerance.equivalent < tolerance.notable                [IS2 验证]
```

**不可机械化的只有：benchmark 跑出来的 delta 够不够小，等效在科学上是否正确。** 那是实验的事。

---

## 五、核心概念速查

### 桥的三维
- **type** (7): implements / refines / substitutes / conflicts_with / tension / equivalence / derives_from
- **mode** (2): independent (逐项独立) / coupled (联合优化, 需外部求解器)
- **layer** (2): declaration (域级, 只声明张力存在, 不含解法) / instance (实例级, 包含解法)

### constraint/boundary 分离
- **constraint formal**: 只写变量关系 (`dist ≤ R`), 不写数值 (`R=4.3`)
- **boundary cost_terms**: 具体代价公式 + 参数 (`L_xtalk = k × (-ln 0.9995)`)
- **instance-space conventions**: 共享测量值 (T2=1.5e6) vs 共享假设 (f_tr≈1)

### 参数三层归属
- `domain/` → 结构 (R_blockade 存在)
- `instance-space/` → 共享测量值 (R_blockade=4.3)
- `instances/*/boundaries/` → 私有近似 (f_2q_idle 公式)

### 尺子是 instance-space 的最小存在条件
没有尺子 = 场景描述, 不是实例空间。尺子 = (metric, formula, tolerance) 三元组。

### Rule of Three — 域级桥声明
第一个实例建实例桥。第二个实例面对同一对约束时等效声明用 `via` 引用约束对。第三个实例出现时建域级桥声明 BD-xxx, 前两个实例的桥回溯补 `declares: BD-xxx`。

---

## 六、六桥基准数据

| Bridge | ZAP 默认 | 替代方案 | Δ (TQE 10-30q) | 敏感性 |
|--------|---------|---------|-----------------|--------|
| BR-keep-vs-move | hard_threshold (Eq.15) | AL 软决策 | 0 | **高** (always_stay 炸) |
| BR-parallel-vs-distance | λ=1000 | 电路自适应 | 0 | 无 |
| BR-parking-displacement | 1 site | 5 sites | <0 (更差) | 弱 |
| BR-asap-strategy | separate | joint | 0 | 无 |
| BR-qubit-priority | 1/(l+1) | reuse-aware | 0 | 无 |
| BR-idle-cost-alpha | α=1.0 | α∈[0.5,5.0] | α=5 掉 | 中 |

---

## 七、下一步（12 周研究计划摘要）

| 周 | 做什么 | 产出 |
|----|--------|------|
| 1–2 | WP0: 不规则电路 benchmark 扩展 (QRAM/VQC/multiplier) | D1 扩展对比表 |
| 3–6 | WP1: 4 维灵敏度扫描 (f_tr × f_xtalk × T2 × a_max) → 危险区 → 自适应 α | D2 热力图 |
| 7–10 | WP2: zone sizing 电路自适应 + slot 压力测试 | D3 zone 曲线族 |
| 11–12 | WP3: 综合写作 + BRIDGE 核查 | D4 技术报告草稿 |

建议补充的工作 (不在这 12 周内，但结构已就位):
- ZAC 实例补边界和桥 (`instances/ZAC/boundaries/` + `bridges/`)
- 加 scalability 和 noise-sensitivity 两个新实例空间
- 让实验脚本从 YAML 读参数 (绑定 protocol.yaml → 实验执行)
- 域级桥声明 (第三个编译器 BRIDGE 加入后触发 Rule of Three)

---

## 八、关键文件索引

| 想了解… | 读这个 |
|---------|--------|
| 项目整体介绍 | `README.md` |
| 四层架构完整设计 | `d:/constraint-engineering-lab/docs/framework-full-architecture.md` |
| 研究计划 (给胡孟军看) | `docs/RESEARCH.md` |
| 已完成工作详录 | `docs/SUMMARY.md` |
| ZAP 论文深度解读 | `d:/constraint-engineering-lab/06-quantum-compiler/ZAP-paper-reading.md` |
| 六桥优化全景 | `d:/constraint-engineering-lab/06-quantum-compiler/OPTIMIZATION.md` |
| ZAP 论文 18 条局限 | `d:/constraint-engineering-lab/06-quantum-compiler/PLAN.md` |
| Fidelity 模型实现 | `domain/formulas/fidelity.py` |
| Keep-vs-move 适配器 | `instances/ZAP/adapter.py` |
| 约束一致性检查规则 | `framework/check.py` |
| Bridge 数据模型 | `framework/schema.py` |

---

## 九、母仓库

这个项目是从 `d:/constraint-engineering-lab/` 的 `06-quantum-compiler/` 练兵场独立出来的。母仓库包含：
- 约束式工程框架 (`_framework/` — check.py 的完整版, 35 条规则, 65 篇理论文档)
- 5 个其他练兵场 (优化/控制/几何/强化学习/概率)
- `_examples/constraint-project/` — 框架的标准答案示例

本项目的 `framework/` 是母仓库 `_framework/` 的轻量剪裁版——只保留了量子编译器域需要的部分。
