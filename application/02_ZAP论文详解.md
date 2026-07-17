# 02 — ZAP 论文技术详解

> 原文：*ZAP: Zoned Architecture and Performant Compiler for Field-Programmable Atom Array*
> Chen Huang, Xi Zhao, Hongze Xu, Weifeng Zhuang, **Meng-Jun Hu\***, Dong E. Liu, Jingbo Wang
> IEEE Transactions on Quantum Engineering, 2026 | arXiv:2411.14037

本文是对 ZAP 论文的逐组件技术解读，标注了每个组件与我的六桥分析的对应关系。

---

## 一、分区架构 (Zoned Architecture)

芯片被物理划分为两个区域：
- **存储区 (SLM)**：静态光阱阵列，间距 6μm。原子在此做单比特门，深阱保证长相干时间
- **纠缠区 (SLM + 全局里德堡激光)**：成对光阱（对内间距 4μm < R_blockade ≈ 4.3μm，对间间距 ≥ 6μm），全局里德堡激光覆盖。只有进入此区的原子才能做双比特门
- 两区间距 10μm，AOD 负责区间搬运

**架构意义**：不是 ZAP 发明的（Lukin 组先做了实验验证），但 ZAP 是第一个把这个架构的编译潜力挖到底的。物理隔离 → 空闲原子不会暴露在里德堡激光下 → 串扰从根源上被压制。编译器问题从"在平地上同时管串扰和搬运"简化为"在两个区域之间做进出决策"。

**六桥对应**：Zone 架构是所有桥的共同硬件前提。keep-vs-move 桥直接依赖 zone 的存在——没有 zone 就没有"搬回存储区"的选项。Enola（单区架构）没有这座桥，它的串扰损失（Fig.7 crosstalk 项）显著高于 ZAP。

---

## 二、保真度模型 (Fidelity Model, Eq.4)

```
f = (f_1)^g1 · (f_2)^g2 · (f_xtalk)^N_xtalk · (f_tr)^N_tr · Π_q exp(-t_q/T2)
```

五项分别对应：单比特门错误、双比特门错误、串扰错误、搬运错误、退相干错误。

前两项由硬件参数决定（编译器不可优化），后三项是编译器可以影响的：
- **N_xtalk**：空闲原子被里德堡激光照射的次数 → keep-vs-move 决策直接影响
- **N_tr**：原子搬运（AOD↔SLM 转乘）的次数 → placement + routing 决策影响
- **t_q**：每个比特的总空闲时间 → 调度策略影响

**模型的隐含假设**：所有错误独立、指数衰减、f_tr 是常数（0.999）、f_xtalk 是全局常数（0.9975）。这些假设在多大参数范围内成立、在什么条件下破缺——是申请后续方向一（物理缺陷测绘）的核心问题。

**六桥对应**：fidelity 公式是六桥的"会计系统"——每座桥的替换最终都折算为公式中某几项的变化。三编译器交叉验证（Enola 5/5, ZAC 6/6）确认了这个公式在不同编译器上的 accounting 一致性。

---

## 三、ASAP-separate 调度

**核心思想**：先把所有 CZ 门按 ASAP 贪心排完，再把单比特门填充到剩余时间槽。

ZAP 的选择是"宁可 stage 数多一点，也不让原子来回搬"——因为搬运时间（微秒级物理移动）比单比特门时间（纳秒级激光脉冲）贵几个数量级。这是整篇论文最关键的 trade-off 判断：**搬运开销 > stage 深度开销。**

**六桥对应**：BR-asap-strategy。对比方案 ASAP-joint 将所有门类型混排 → stage 更少但原子在"需要纠缠"和"不需要纠缠"之间反复横跳 → 搬运次数暴增。我的 swap 实验确认：在 TQE benchmark 尺度上，separate 和 joint 的 fidelity 差异为 0（平台期效应）。

---

## 四、确定性单遍布局 (Deterministic Single-Pass Placement)

**初始布局 (Initial Mapping)**：把最重要的比特（参与早期门的、参与次数多的）优先分配到离纠缠区最近的存储坑位。分配时计算 AOD 兼容性分数——如果选这个坑，将来第一次搬进纠缠区的移动方向是否会跟已分配比特的移动方向冲突。公式 (11)：

```
score(u) = λ_par × c(u) + d_min(u)
```

λ_par 控制并行度 vs 搬运距离的权衡权重（默认 1000）。

**逐 stage 布局 (Stage-Wise Placement)**：对已在纠缠区但当前没有门任务的比特做 keep-vs-move 决策；对当前有门任务的比特，在空闲纠缠坑对中选移动距离最短 + AOD 冲突最少的那一对。

**六桥对应**：placement 模块涉及三座桥——keep-vs-move（空闲比特管理）、parallel-vs-distance（λ_par 权重）、qubit-priority（初始布局时的比特权重）。

---

## 五、冲突感知路由 (Conflict-Aware Routing + Parking)

AOD 只能沿行或沿列移动原子，且同一行/列的原子必须步调一致。路由不是经典最短路径——是带并行度约束的协调调度。

**核心策略**：
- 安全向量提取（只移动目标坑位没被占的原子）
- AOD 兼容性图（两个原子能否并行搬运取决于行列轨迹是否冲突）
- 兼容性图上的贪心最大独立集（每次挑一批互不冲突的原子并行搬）
- Parking：路线冲突时短暂横移一个原子，错开身位后并行搬运

**六桥对应**：BR-parking-displacement。ZAP 固定 parking 位移为 1 site。我的 swap 实验测试了 5 site displacement → fidelity 略微下降（Δ=-0.0001），符合预期——多搬 = 多损耗。

---

## 六、空闲比特管理 (Idle-Qubit Management) — 最重要的一节

这是 ZAP 中与我的分析关联最深的部分。公式 (12)-(15) 三步算账：

1. **串扰损失 L_xtalk**：留下会被里德堡激光照射几个 stage × 每次照射的保真度损失
2. **搬运损失 L_tr**：搬回存储区需要几次 AOD-SLM 转乘 × 每次转乘损失
3. **退相干损失 L_dec**：搬运额外花费的时间 / T2

决策（Eq.15）：`if L_xtalk > L_tr + L_dec → move; else → stay`

这是 **per-qubit、per-stage 的独立决策**——每个比特单独算账，不和任何其他比特协调。

**六桥对应**：BR-keep-vs-move。这是我的核心改进点。ZAP 的 Eq.15 是线性冲突函数（硬阈值），我的 AL 软决策替换为：连续权重 w∈[0,1] + 全局 slot 容量约束 → 联合优化。在 slot 紧约束时，硬阈值的独立决策导致系统性 over-commit（violation 168→0）。

**胡孟军老师的三支冲突分析与这个改进的关系**：Eq.15 是二支决策（搬/不搬，无 DEFER 区间）。连续权重 w∈[0,1] 引入了 DEFER 状态——当 w≈0.5 时系统不确定该搬还是该留，让联合优化来消解。这正是三支决策在编译器域的实例化。

---

## 七、实验部分的关键图表

- **Fig.7 (fidelity breakdown)**：四编译器保真度拆解。Enola 的 crosstalk bar 显著高于 ZAP——zone 架构的物理隔离效果一目了然
- **Fig.9 (compiler-dependent loss)**：只比编译器能控制的错误通道（搬运、退相干、串扰），排除硬件决定的 gate fidelity。最诚实的比较方式
- **Fig.13 (ablation: keep vs move)**：三组 benchmark × 三种策略（Dynamic / Always-Move / Always-Stay）。这是论文中对我的分析最重要的一张图——Always-Stay 在 qram_n20 上串扰炸了（保真度崩塌），ZAP 动态策略拿到了最好的平衡
- **Fig.14 (parameter sensitivity heatmap)**：f_tr × f_xtalk 参数空间上 ZAP vs PowerMove 的 ERR。结构化 benchmark（qram_n20）上 ZAP 在"串扰严重 + 搬运可靠"区域优势最大

---

## 八、论文的诚实限定

- "随机 3-正则图上 ZAP 和 PowerMove 的差距缩小"——承认随机图缺乏高对比度结构，编译器优势被均化
- "ZAP 不是严格线性复杂度"——初始布局最坏 O(N³)，但在硬件约束下实际表现接近线性
- "我们 claim 的是实用可扩展性，不是渐近最优性"——诚实的工程论文口吻

---

## 九、我的三个切入方向

按可行性排序：

### 方向 1：keep-vs-move 软决策化（已完成初步验证）

Eq.15 硬阈值 → AL 联合优化。已完成：紧 slot 试验显示 violation 168→0。待做：在真实 benchmark 上跑更全面的对比。

### 方向 2：物理缺陷测绘

ZAP fidelity 模型的五个过度简化：
- 搬运-退相干耦合被忽略（搬一个、全体扣 T2）
- 里德堡阻塞是概率性的（对间距是编译参数不是硬件常数）
- f_tr 不是常数（是距离/速度/trap depth 的函数）
- SLM 阵列不均匀（存在好坑坏坑）
- 串扰空间依赖性（边缘比中心安全）

测绘成立的参数范围 → 建立 ZAP 编译策略的物理适用地图。

### 方向 3：三支冲突分析 × 编译器桥

胡孟军老师的三支冲突分析（IEEE TFS 2026, IJAR 2026）为编译器决策的形式化提供了理论地基。桥的 resolve_fn 是冲突函数——线性（Eq.15）→ 非线性（AL）→ 全域（跨编译器统一的决策框架）。
