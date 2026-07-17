# 工作总结 — ZAP 编译器分析

> 2026-07-15 ~ 2026-07-17

---

## 一、做了什么

### 1. 六桥基准测试

ZAP 的 6 个决策点形式化为桥，逐一 monkey-patch 替换，TQE benchmark 套件对比：

| 桥 | ZAP 默认 | 替代方案 | Δ Fidelity | 敏感性 |
|---|---|---|---|---|
| keep-vs-move | hard_threshold Eq.15 | AL 联合优化 | 0 | **高** (slot violation 170→0) |
| parallel-vs-distance | λ=1000 | 电路自适应 | 0 | 低 |
| parking-displacement | 1 site | 5 sites | -0.0001 | 中 |
| asap-strategy | separate | joint | 0 | 低 |
| qubit-priority | 1/(l+1) | reuse-aware | 0 | 低 |
| idle-cost-alpha | α=1.0 | α=2.0 | 0 | 低 |

**核心发现**：5/6 的桥已达 fidelity 平台期。只有 keep-vs-move 存在结构性优化空间——不是 fidelity Δ，而是 slot 容量约束下的系统性违反。

### 2. keep-vs-move：硬阈值 → AL 联合优化

ZAP Eq.15 是 per-qubit 独立硬阈值（`if L_xtalk > L_tr + L_dec → move`），不考虑有限 slot 容量。

AL 软决策：连续权重 w∈[0,1] + 全局 slot 约束 Σ(1−w_i) ≤ slot_count → 增广拉格朗日联合求解。

| 场景 | hard_threshold | AL soft |
|---|---|---|
| 宽松 slot (4 for 20q) | fidelity 0.89, 0 violation | fidelity 0.88, 0 violation |
| 紧 slot (3 for 20q) | **170 violations** | **0 violations** |

**AL 不伤害常规场景 fidelity，紧 slot 下消除所有约束违反。结构性修复，不是参数调优。**

### 3. 三编译器 Fidelity 交叉验证

同一公式（ZAP Eq.4），验证三个编译器的内置仿真器：

| 编译器 | 架构 | 结果 |
|---|---|---|
| Enola (UCLA-VAST) | 单区，无 zone | 5/5 PASS |
| ZAC (UCLA-VAST, HPCA 2025) | zone，模拟退火迭代 | 6/6 PASS |
| ZAP (BAQIS, IEEE TQE 2026) | zone，单遍确定性 | 内置自洽 |

### 4. ZAP 原始 Benchmark 复现

5 个代表性电路在本地环境复现，fidelity 与论文 Fig.7 差异 < 0.001。

| Benchmark | 我们的复现 | 论文 | Δ |
|---|---|---|---|
| QFT (n=10) | 0.5029 | 0.503 | -0.0001 |
| Ising (n=26) | 0.6578 | 0.658 | -0.0002 |
| GHZ (n=30) | 0.6433 | 0.643 | +0.0003 |
| QRAM (n=20) | 0.3584 | 0.358 | +0.0004 |
| Multiplier (n=15) | 0.0824 | 0.082 | +0.0004 |

---

## 二、项目状态

- 7 个实验脚本，全部可独立运行
- 申请材料包（4 份文档 + 5 张图）
- ZAP 完整复现流程
- Python 3.12 + venv + requirements.txt
- 框架自检 0 FAIL

---

## 三、真正的优势

**methodology 不依赖 ZAP 源码细节。** ZAP 的 placer.py 把串扰代价计算和贪心坑位选择写在同一个 for 循环里。桥的视角把它们拆成约束声明（source/target）和求解策略（resolve_fn）。替换一个决策不需要理解全部 placement 逻辑——只需要定位 monkey-patch 注入点。

**六座桥，几分钟跑完，不改 ZAP 源码。** 框架快速排除 5 个无效方向，聚焦唯一有价值的目标。

**AL 软决策和三支冲突分析是同构的。** hard_threshold 是二支决策（搬/不搬），AL 的连续权重 w∈[0,1] 引入了 DEFER 区间——恰好是胡孟军三支冲突分析（IEEE TFS 2026）在编译器域的实例化。这是在胡老师两个独立研究方向之间架桥的天然切入点。

---

## 四、局限与下一步

1. 紧 slot 实验是 synthetic stress test，未在真实 benchmark 上验证 AL 的优势
2. 其余五座桥的替代策略是简单替换，未做电路自适应优化
3. fidelity 模型假设错误独立——五个物理过度简化（搬运-退相干耦合、阻塞概率性、f_tr 空间依赖、SLM 不均匀、串扰空间依赖）尚未测绘
4. 跨编译器桥分析方法仅在 ZAP 上完整展开，Enola/ZAC/PowerMove 待覆盖

**下一步（见 ROADMAP.md）**：物理缺陷测绘 → 紧 slot 在真实 benchmark 验证 → 跨编译器推广 → 三支冲突分析 × 编译器桥的形式化。
