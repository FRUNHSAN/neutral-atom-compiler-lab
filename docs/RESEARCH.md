# 研究计划书

> 面向：胡孟军团队（ZAP, IEEE TQE 2026）
> 周期：3 个月（12 周），实验 + 文献并行
> 基础：ZAP 开源代码 + 已完成的六桥基准与三编译器 fidelity 交叉验证

---

## 摘要

ZAP 论文在 §VII-D-2 和 §IX 留下了两个明确的扩展空间：
1. **硬件参数灵敏度分析只扫了 2 维**——论文承认在 movement-dominated 硬件下 ZAP 的优势可能变负
2. **future work 第一项就是 storage/entanglement zone 协同设计**

本计划分别对应：把灵敏度分析扩展到 4 维并刻画 ZAP 的"危险区"与自适应修复方案；把纠缠区大小从固定常量变成电路自适应的编译变量。

**前期工作（已完成，12 commits）**：在不改 ZAP 源码的前提下替换了全部 6 个决策点，在 3 类电路上完成基准对比；同一 fidelity 公式交叉验证了 Enola / ZAC / ZAP 三个编译器（11/11 PASS）。核心发现：6 个决策点中只有 keep-vs-move 是高敏感性参数——下一步的收益不在调参，而在参数的"硬件/电路条件化"。

---

## 一、问题陈述

ZAP 用确定性单遍编译换来了 1000×+ 的编译速度，代价是所有决策参数都是**离线固定值**。论文的两处自我声明暴露了固定值的边界：

1. **§VII-D-2**："ZAP's relative advantage narrows and can become neutral or slightly negative in movement-dominated regimes." —— 但论文只给了 2 幅热力图（扫 f_tr × f_xtalk）。T2 更短、搬运加速度受限、纠缠区更拥挤的参数组合未探索。

2. **§IX**："Future work includes exploring the co-design space of storage and entanglement zones." —— 当前 zone 配置固定（存储 80 阱 / 纠缠 160 阱），但纠缠区大小存在基本 trade-off：太小 → slot 不够 → 搬运增多；太大 → 更多原子暴露在里德堡激光下 → crosstalk。

**研究问题**：ZAP 的固定参数在哪些（硬件 × 电路）条件下退化？退化能否用不破坏单遍范式的自适应规则修复？

---

## 二、研究内容（4 个工作包）

### WP0 · benchmark 扩展到不规则电路（第 1–2 周，地基）

- 把 QRAM 树形、VQC、multiplier 等不规则电路加入 benchmark
- 在扩展套件上重跑全部六桥 swap
- **预期产出 D1**：扩展对比表；预计 λ_par 与 parking 在 QRAM 上首次出现非零 Δ

### WP1 · 4 维硬件参数灵敏度（第 3–6 周）

- 扫 4 维参数空间：f_tr × f_xtalk × T2 × a_max
- 每个参数点跑 ZAP vs PowerMove vs ZAC
- 识别 ERR < 0 的"危险区"
- 危险区内测试自适应 keep-vs-move（idle_cost_alpha 为硬件参数的函数）
- **预期产出 D2**：4 维 ERR 热力图 + 危险区边界 + 自适应 α 规则

### WP2 · 纠缠区大小电路自适应（第 7–10 周）

- 纠缠区大小做成可调变量（4 对 → 160 对）
- 跨电路扫描最优 zone 大小
- slot 压力测试：压缩纠缠区到 2–8 对，对比硬阈值 vs AL 软决策
- **预期产出 D3**：zone 大小-fidelity 曲线族 + 最优值的电路依赖规律

### WP3 · 综合与写作（第 11–12 周）

- 汇总 D1-D3，形成技术报告 / workshop 论文草稿
- 备选延伸：贪心 MIS → 精确 MIS + timeout fallback；500→2000 qubit scalability 复现

---

## 三、时间线

| 周 | 实验 | 文献 | 里程碑 |
|----|------|------|--------|
| 1–2 | WP0 benchmark 扩展 | Tier 1 精读 | D1 扩展对比表 |
| 3–6 | WP1 四维灵敏度扫描 | Tier 2 谱系 | D2 危险区刻画 |
| 7–10 | WP2 zone sizing | Tier 3 前沿 | D3 zone 曲线族 |
| 11–12 | WP3 综合写作 | 补漏整理 | D4 技术报告草稿 |

---

## 四、方法论

所有实验用桥接方法论组织：ZAP 的每个决策点注册为一座"桥"，每次参数/策略替换是一次桥的 swap。前期六桥基准测试证明了该方法的效率：**六个决策点、三类电路、九分钟跑完、零行 ZAP 源码改动**——快速排除五个无效方向，聚焦唯一的高敏感性参数。
