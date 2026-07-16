# 工作总结 — ZAP 编译器分析

> 2026-07-15 ~ 2026-07-16，12 commits

## 一、做了什么

### 1. 六桥基准测试

ZAP 的 6 个决策点，逐一 monkey-patch 替换，3 种电路对比：

| Bridge | 默认 | 替代 | Δ | 敏感性 |
|--------|------|------|-----|--------|
| BR-keep-vs-move | lookahead 硬阈值 | AL 软决策 | 0 (此规模) | **高** |
| BR-parallel-vs-distance | λ=1000 | 电路自适应 | 0 | 无 |
| BR-parking-displacement | 1 site | 5 sites | <0 | 弱 |
| BR-asap-strategy | separate | joint | 0 | 无 |
| BR-qubit-priority | 1/(l+1) | reuse-aware | 0 | 无 |
| BR-idle-cost-alpha | α=1.0 | α∈[0.5,5.0] | α=5 掉 | 中 |

**核心发现：6 个决策点中只有 keep-vs-move 是高敏感性参数。ZAP 默认值已近最优。**

### 2. 三编译器 Fidelity 交叉验证

同一公式（Eq.4），验证三个编译器的内置模拟器：

| 编译器 | 结果 | 关键发现 |
|--------|------|---------|
| Enola | 5/5 PASS | 无 zone → crosstalk=0.975 |
| ZAC | 6/6 PASS | zone 架构 → crosstalk=1.0 |
| ZAP | 内置一致性 | 三策略对比：lookahead/always_move/always_stay |

### 3. 跨编译器 benchmark

同一电路（toy2），Enola vs ZAC：
```
                 Enola (no zone)    ZAC (zone)       Delta
Crosstalk:       0.975              1.000           +0.025
Transfer:        0.968              0.938           -0.031
TOTAL:           0.883              0.887           +0.39%
```
zone 的 crosstalk 收益被搬运代价抵消大半，净赢 0.39%。

### 4. ZAP 策略对比

ZAP 三策略（qft_n10）：
```
                 Fidelity  Crosstalk  Duration
lookahead(ZAP):  0.509     1.000      7980μs
always_move:     0.503     1.000      7905μs
always_stay:     0.420     0.802      6768μs  ← 串扰 -20%
```
always_stay 的 fidelity 崩了——空闲 qubit 留在纠缠区被激光照。

---

## 二、框架撞出的东西

1. **cost model 属于 boundary，不属于 constraint** — constraint 管"什么是对/错"，boundary 管"错了扣多少分"
2. **求解策略不是约束** — greedy MIS、parking 启发式不是约束，是满足约束的算法
3. **转化率不是目标** — ZAP 52% 是求解器代码，不转化是对的
4. **可执行 discretization_gap** — 从 YAML 声明变成 benchmark 测量
5. **benchmark-driven 验证** — 不是 assert，是跑电路 → 比保真度 → 出对比表

---

## 三、真正的优势

**它把"应该是什么"和"怎么做到"分开了。** ZAP 的 placer.py 里这两个混在一起：串扰代价计算和贪心坑位选择写在同一个 for 循环里。框架把它们拆成 constraint 声明和 implementation。改约束只改声明，换求解策略只换 adapter，不改的不受影响。

**六个决策点，九分钟跑完，不改 ZAP 源码。** 如果每次替换都要改 ZAP 源码、重新理解 placement 逻辑，六次替换要花六天。框架九分钟排除五个。

---

## 四、局限

1. 所有实验在 10–30 qubit 规模
2. 六座桥，零座赢过 ZAP 默认参数——框架证明了"能换"，没证明"换了更好"
3. 1005 行求解器完全没碰——greedy MIS、placement heuristics 的替换是最核心的改进方向
