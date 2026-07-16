# neutral-atom-compiler-lab

> 中性原子量子编译器分析——从 ZAP 范式边界测绘到编译器对比方法论。
> 面向北京量子信息科学研究院 2026 年"量子青年人才储备计划"，目标导师：胡孟军。

## 一句话

我在不修改 ZAP（IEEE TQE 2026）源码的前提下，用 monkey-patch 替换了它的全部 6 个决策点，在 3 类电路上完成基准对比；并用同一 fidelity 公式交叉验证了 Enola / ZAC / ZAP 三个编译器的内置模拟器（11/11 PASS）。下一步：把 ZAP 的固定参数变成硬件和电路自适应参数，测绘单遍确定性编译范式的适用边界。

---

## 做了什么（12 commits，已完成）

### 六桥基准测试

ZAP 的 6 个决策点全部做了桥接——不改源码，用 monkey-patch 替换每个决策逻辑，在 QFT / Ising / GHZ 三类电路上对比默认参数 vs 自适应替代：

| Bridge | ZAP 默认 | 替代方案 | Δ | 敏感性 |
|--------|---------|---------|------|--------|
| BR-keep-vs-move | lookahead 硬阈值 | AL 软决策 | 0 (此规模) | **高** |
| BR-parallel-vs-distance | λ=1000 | 电路自适应 | 0 | 无 |
| BR-parking-displacement | 1 site | 5 sites | <0 (更差) | 弱 |
| BR-asap-strategy | separate | joint | 0 | 无 |
| BR-qubit-priority | 1/(l+1) | reuse-aware | 0 | 无 |
| BR-idle-cost-alpha | α=1.0 | α∈[0.5,5.0] | α=5 掉 | 中 |

**核心发现：6 个决策点中只有 keep-vs-move 是高敏感性参数。ZAP 默认值已近最优。** 六桥 swap 9 分钟跑完——快速排除 5 个无效方向，聚焦唯一的敏感参数。

### 三编译器 Fidelity 交叉验证

用 ZAP 论文 Eq. 4 作为统一 fidelity 公式，独立复现三个编译器的内置模拟器：

| 编译器 | 验证结果 | 关键发现 |
|--------|---------|---------|
| Enola | 5/5 PASS | 无 zone → crosstalk=0.975 |
| ZAC | 6/6 PASS | zone 架构 → crosstalk=1.0（消除） |
| ZAP | 内置一致性 | 三策略对比：lookahead/always_move/always_stay |

---

## 项目结构

```
neutral-atom-compiler-lab/
├── README.md              ← 你在这里
├── CLAUDE.md              ← 项目指令
├── pyproject.toml
├── src/nac_lab/
│   ├── fidelity.py        ← 独立 Eq. 4 fidelity 模型
│   ├── adapter.py         ← ZAP 域适配器（硬阈值 + AL 软决策）
│   └── bridges.py         ← 桥接基础设施
├── experiments/
│   ├── bridge_swap.py     ← 六桥完整 swap 实验
│   ├── cross_validate.py  ← 三编译器 fidelity 交叉验证
│   ├── strategy_compare.py← 硬阈值 vs AL 软决策对比
│   └── lambda_par_swap.py ← λ_par 参数扫描
├── docs/
│   ├── RESEARCH.md        ← 研究计划书（3 个月，4 个工作包）
│   ├── SUMMARY.md         ← 已完成工作总结
│   └── reading/           ← 文献阅读笔记
├── constraints/
│   └── quantum_compiler.yaml ← 10 条量子编译器约束定义
└── results/               ← 实验输出
```

---

## 3 个月研究计划（如果加入课题组）

### WP0 · 基准扩展（第 1–2 周）
扩展不规则电路（QRAM 树形、VQC、multiplier）→ 在不规则电路上重跑六桥，预计 λ_par 与 parking 首次出现非零 Δ。

### WP1 · 4 维灵敏度 + 危险区测绘（第 3–6 周）
扫 f_tr × f_xtalk × T2 × a_max → 刻画 ZAP 的安全区/危险区边界 → 危险区内测试自适应 keep-vs-move（idle_cost_alpha 条件化）。

### WP2 · zone sizing 电路自适应（第 7–10 周）
纠缠区大小从固定值变成电路自适应的编译变量 → 跨 QFT/QRAM/Ising/GHZ 扫描最优 zone 大小 → 提出"编译前根据电路 DAG 并行度估算纠缠区"。

### WP3 · 综合写作 + BRIDGE 核查（第 11–12 周）
用交叉验证能力核查 BRIDGE (arXiv:2606) 声称 "fidelity ~10× 优于 ZAP" 的对比口径 → 产出技术报告 / workshop 论文草稿。

---

## 为什么选中性原子编译器

1. **双维度耦合**（空间搬运 + 时序调度）→ 编译器复杂度恰好够，又恰好可穷举
2. **硬件参数仍在快速演化**（2022 年才首次展示相干搬运，参数每年在变）
3. **6+ 个竞争编译器**（Enola / ZAC / PowerMove / ZAP / NALAC / Arctic / BRIDGE）→ 交叉验证有真活可干
4. **范式窗口**（DT 定向传输、BRIDGE 双物种 2026 年正在从硬件层挑战搬运范式）

换个平台（超导/离子阱/光子），要么约束太简单、要么硬件已定型、要么交叉验证没必要——都没法构成完整的验证集。

---

## 快速开始

```bash
# 安装依赖
pip install -e .

# 跑 fidelity 交叉验证
python experiments/cross_validate.py

# 跑六桥 swap（需要 ZAP 源码路径）
python experiments/bridge_swap.py --zap-path <path-to-zap>

# 跑硬阈值 vs AL 软决策对比
python experiments/strategy_compare.py
```

---

## 联系方式

- 作者：[你的名字]，大三本科生
- 目标：北京量子信息科学研究院 胡孟军 课题组
- 项目性质："量子青年人才储备计划"申请材料的一部分
