# neutral-atom-compiler-lab — 中性原子量子编译器分析

> 独立研究项目。用桥接方法论拆解中性原子量子编译器的决策空间，
> 以 ZAP (IEEE TQE 2026) 为第一个完整分析对象。

## 启动序列

```
1. pip install -e .
2. python experiments/cross_validate.py    ← 验证 fidelity 模型
3. python experiments/strategy_compare.py  ← 硬阈值 vs AL 软决策
4. python experiments/bridge_swap.py --zap-path <path>  ← 完整六桥 swap
```

## 项目目的

1. **分析层**：测绘 ZAP 编译器单遍确定性范式的适用边界
2. **方法层**：验证桥接方法论在真实编译器上的分析能力
3. **产出层**：为 BAQIS "量子青年人才储备计划"申请提供可核查的技术基础

## 核心概念

### 桥 (Bridge)
编译器的一个决策点——在不改源码的前提下可被替换。桥声明了：
- 干什么的 (type + source_constraint → target_constraint)
- 怎么替换 (resolve_fn + adapter)
- 替换后怎么比 (benchmark + fidelity model)

### Fidelity 模型 (Eq. 4)
统一的跨编译器 fidelity 公式：
```
F_total = F_1q × F_2q × F_xtalk × F_transfer × F_coherence
```
- F_1q = 单比特门保真度（各编译器相同）
- F_2q = 双比特门保真度（f2^count）
- F_xtalk = 串扰保真度（f2q_idle^exposures）
- F_transfer = 搬运保真度（f_tr^transfers）
- F_coherence = 退相干保真度（exp(-t/T2) 或线性近似）

### 六桥
ZAP 的 6 个决策点：
1. **keep-vs-move**：空闲比特留在纠缠区还是搬回存储区（唯一高敏感性参数）
2. **λ_par**：并行化 vs 搬运距离的权衡权重
3. **parking**：搬回存储区时的坑位选择策略
4. **ASAP**：调度策略（separate / joint）
5. **qubit priority**：哪几个比特优先占纠缠区槽位
6. **idle_cost_alpha**：闲置代价和搬运代价的换算系数

## 关键约束

- 不改 ZAP 源码——所有决策点替换通过 monkey-patch 或架构 JSON 注入
- 同一 fidelity 公式跨编译器对比——避免口径差异
- 所有实验可复现——脚本参数化，结果可重跑
- 不依赖外部框架——本项目自包含，不依赖 constraint-engineering-lab 的 _framework/

## 相关项目

- ZAP：https://github.com/BAQIS-Quantum/neutral-atom-compilation（MIT 许可证）
- Enola：https://github.com/UCLA-VAST/Enola
- ZAC：https://github.com/UCLA-VAST/ZAC
- PowerMove：https://github.com/Scarlett0815/PowerMove
- 本项目的母仓库：constraint-engineering-lab（D:/constraint-engineering-lab/）
