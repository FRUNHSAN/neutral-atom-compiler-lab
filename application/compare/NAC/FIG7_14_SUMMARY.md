# ZAP vs NAC — Fig.7 ~ Fig.14 对比总表

> 更新：2026-07-22 | 策略：`asap_separate` | 架构：`scale_to_500.json` | benchmark：同一套 QASM 文件

| 图 | 内容 | ZAP | NAC | 关键差异 |
|---|---|---|---|---|
| Fig.7 | 保真度分解(14bench) | F_2q/F_idle/F_tr/F_dec堆叠 | 同公式，F_2q 14/14 完全一致 | Mean \|delta\|=2.0%，13/14 ±5%；sat_n11 NAC +6.4% (alpha=1.0 反超 ZAP)；wstate_n27 NAC -4.1% (最差偏离) |
| Fig.8 | 随机3-正则scaling | N=10→100 趋势 | N=10 F=0.83 → N=100 F=0.027 | F_tr 低 5-10%，随机图无结构可 exploit，placer 权重均匀化是根本原因，site 排序修复后无改善 |
| Fig.9 | 编译器依赖通道 | F_idle×F_tr×F_dec | 同度量 | NAC 偏 F_tr (少搬、快)、ZAP 偏 F_idle (少串扰)，同一 trade-off 的两个方向 |
| Fig.10 | 执行时间 | ZAP baseline | NAC 系统性偏短 10-37% | alpha=1.0 偏"留着"，少搬运 → 快执行；ZAP alpha≈0.7 偏"搬回" |
| Fig.11 | 编译时间(14bench) | <0.3s | 0.02-0.3s (小电路慢 2-3×) | Python 常数开销；但 sat_n11/vqc_n15 等密集电路持平 (<0.3s) |
| Fig.12 | 可扩展性(→500q) | Ising: 0.6→30s O(N)；QFT: N=150 316s → N=200 1212s (20min) | Ising: 1.3→50s O(N)；QFT: N=150 31.5s O(N) | Ising: NAC 慢 2-3×；Cat: NAC 快 5× (at 200q)；Adder: N=64 交叉，N=136 NAC 快 3× (18s vs 61s)；QFT: N=150 NAC 快 10× (32s vs 316s) |
| Fig.13 | 消融(3策略) | baseline≈always_move | baseline 居间：stay 最快/move 最慢；执行时间 1-47ms | NAC alpha=1.0 偏 stay，baseline < always_move (同 ZAP 方向)，但 ZAP alpha≈0.7 让 baseline 更接近 move |
| Fig.14 | 灵敏度热力图 (qft_n10) | ZAP vs PowerMove ERR | baseline vs always_move ERR | ERR 全负 ≈ -0.1 (at 默认参数 ★)；f_tr↑→ERR→0 (搬运便宜则 Dynamic→AlwaysMove)；f_tr↓→ERR 最负 -0.17 |
| — | ASAP策略 (separate vs joint) | asap_joint 快 1.8-3.6× (避免 O(N³) 1q-fitting)；N=150: 315s → 88s | asap_separate 快 1.3× (stage 少 2.8×，router 省工)；N=150: 31s → 41s | **方向相反**：ZAP separate 的 1q-fitting 做跨 qubit 兼容检查（O(N³)），joint 逃过；NAC 不做跨 qubit 检查（O(N)），separate 反而 stage 更少 → router 更快 |
| ★ | 距离依赖串扰 (van der Waals) | 二值模型：纠缠区内全计数 | 距离衰减 w(d)=1/(1+(d/R_blockade)⁶) | sat_n11: +56.9% vs ZAP (0.1307 vs 0.0833)；multiplier_n15: +44.1%；vqc_n15: +41.6%；knn_n25: +23.7%。稀疏电路 idle qubit 离活跃对远 → ZAP系统性高估串扰。placer 也用了距离权重做 stay/move。详见 .ai_reasoning/chains/2026-07-23-distance-crosstalk-model.md |
