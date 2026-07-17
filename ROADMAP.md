# 中性原子量子编译器 — 完整待做事项

> 目标：测绘 ZAP 编译器的物理-决策边界，拿到 BAQIS 科研实习生身份，同时倒逼框架优化。
> 不设时间限制。按依赖关系分层，不是按优先级——每一层的东西都可以在任何时间做。
> 做完一件划一件。新增的补在对应层末尾。

---

## 零、基础清理（让后续工作不拖泥带水）

- [x] **去重 fidelity.py** — 删了 `src/nac_lab/fidelity.py`（死代码，无人引用）。正本：`domain/formulas/fidelity.py`
- [x] **去重 adapter.py** — 删了 `src/nac_lab/adapter.py`（死代码，无人引用）。正本：`instances/ZAP/adapter.py`
- [x] **YAML 保留当 CI 金丝雀** — 13 个 YAML + check.py 保持 0 FAIL。不往里面加新约束，不修规则，不当干活工具。当结构完整性嗅探器
- [x] **实验脚本统一入口** — 去重完成后所有脚本自然共用同一套 import：`domain/formulas/fidelity`（fidelity 模型）+ `instances/ZAP/adapter`（求解器）。不需要额外 config.py——5 个实验脚本 import 链统一
- [x] **baselines/ 路径可配（bridge_swap.py 已修）** — `bridge_swap.py` 的 `--zap-path` 默认值从硬编码 `DEFAULT_ZAP_PATH` 改为 `None`，不再误触发 live ZAP 模式。`lambda_par_swap.py` 仍硬编码，等用到时再修
- [x] **Enola/ZAC/PowerMove baselines 验证** — `baselines/` 中三个编译器源码全部就位。Enola 和 ZAC 能 import，PowerMove 待 clone

---

## 一、ZAP 物理缺陷测绘（核心产出 — 编译器建立在什么物理简化上）

### 1.1 搬运-退相干耦合

- [ ] **集体退相干模型** — 修改 fidelity 计算：AOD 搬运期间，所有原子（不只是被搬的那个）都在持续退相干。代价 = Σ_q exp(-t_transport / T2_q)，不是 per-qubit f_tr
- [ ] **重算 keep-vs-move 决策** — 在集体退相干模型下重新跑六桥 swap，看 keep-vs-move 的"最优"决策是否改变
- [ ] **搬运事件频率 vs 退相干损失的标度律** — n_transport 越大，集体损失越大；定量测绘这个 trade-off
- [ ] **新桥：transport-frequency vs decoherence** — 如果发现集体退相干显著改变了最优决策 → 这是一座 ZAP 没有显式建模的桥

### 1.2 里德堡阻塞的概率性

- [ ] **从硬墙到软概率** — 把 f_xtalk = (f_2q_idle)^(n_exposures) 替换为 per-atom-pair 的概率：P(excitation_both) = f(d_ij/R_blockade)，基于 van der Waals ~1/R⁶
- [ ] **zone 间距扫描** — 不同对间距（3.8, 4.0, 4.3, 4.6, 5.0 μm）下，fidelity-breakdown 的 crosstalk 项怎么变
- [ ] **阻塞泄漏 vs 并行度 trade-off** — 间距小 → 可塞更多对 → 并行度 ↑ → 但阻塞泄漏 ↑。最优间距是电路结构的函数
- [ ] **zone 间距从 Boundary 提升为 Bridge** — 当前 B-zap-hardware 把间距当固定硬件参数。如果它是可优化的编译决策 → 移到 bridge 层

### 1.3 搬运保真度的空间/运动依赖

- [ ] **f_tr(距离, 速度, 位置) 替代常数** — 查文献标定函数形式。大框架：f_tr ≈ exp(-α·d²/v)，α 依赖 trap depth
- [ ] **AOD 边缘 vs 中心的 trap depth 差异** — 高斯光束剖面 → 边缘 trap 比中心浅 → 同距离搬运，边缘原子损失更大
- [ ] **最优搬运速度** — 快搬 → 时间短 → 退相干少 → 但 trap loss 大。慢搬反之。存在一个最优速度。当前 ZAP 固定速度——这是另一个编译器没利用的自由度
- [ ] **新桥：transport-speed vs decoherence** — 搬运速度的 trade-off，又一个 ZAP 没有显式建模的桥

### 1.4 SLM 阵列不均匀性

- [ ] **合成 trap depth 分布** — 用高斯剖面 + 衍射环生成 per-site trap depth。不追求绝对精度——追求合理的非均匀度
- [ ] **好坑/坏坑的初始布局策略** — ZAP 的 init_mapping 只看距离和 AOD 兼容性。如果加上 trap 质量，高重用比特优先放深阱 → fidelity 提升
- [ ] **新桥：trap-quality vs routing-convenience** — placement 时的又一组张力

### 1.5 串扰的空间依赖性

- [ ] **per-site f_xtalk** — 根据到纠缠区中心的距离打分。边缘的空闲原子比中心的空闲原子离里德堡激光更远 → 串扰概率更低
- [ ] **空闲原子的超精细态影响** — 不同初始态（|0⟩, |1⟩, 叠加态）到里德堡态的耦合强度不同 → 串扰敏感性不同。如果编译器知道每个原子的态 → 可以决定"哪个空闲原子留在纠缠区"时考虑态
- [ ] **查文献标定** — 串扰的空间和态依赖有现成文献（Lukin 组、Browaeys 组），拉参数

### 1.6 物理缺陷的综合文档

- [ ] **ZAP 物理模型边界地图** — 五个缺陷各自在什么参数范围内可忽略、在什么范围内破缺。一张表
- [ ] **破缺条件数据库** — f_tr < 0.99 → 搬运保真度假设破缺。T2 < 5e5 → 集体退相干不可忽略。etc.

---

## 二、决策点自动优化（六桥全走一遍）

### 2.1 keep-vs-move（已完成基础版）

- [ ] **AL 软决策 + 集体退相干** — 把 1.1 的集体退相干模型嵌入 AL 的目标函数
- [ ] **AL 软决策 + 鲁棒优化** — 参数不精确取点值，给区间（T2∈[1e6, 3e6], f_tr∈[0.998, 0.9995]），min-max 优化
- [ ] **per-stage warm-start 链测试** — AL 的 initial_guess 从前一阶段传，验证收敛速度是否提升
- [ ] **不规则电路测试** — QRAM/VQC/Multiplier——非均匀重用才是 AL 的用武之地

### 2.2 λ_par（并行-距离权重）

- [ ] **电路特征提取** — 对每个 benchmark 算：CZ 密度、平均比特重用频率、重用频率分布的方差
- [ ] **λ_par 的参数扫描** — 对每个电路扫 λ_par∈[10, 10000]，找最优值，看是否和电路特征相关
- [ ] **自适应 λ_par 映射函数** — 电路特征 → 推荐 λ_par。先做查表，后做拟合
- [ ] **新桥正式化** — BR-parallel-vs-distance 当前是 weighted（固定权重），改成 solver（自适应权重）

### 2.3 parking（坑位选择策略）

- [ ] **parking displacement 扫描** — 1/2/3/4/5 sites，每个 benchmark 跑一遍
- [ ] **parking site 质量权重** — 不只选位移最小的坑位，选"位移 + trap 质量"综合最优的
- [ ] **不搬回原位的 parking** — ZAP 假设搬回存储区时回原来坑位。如果不回原位 → 更多的自由度，但增加了 fragmentation。做对比实验

### 2.4 ASAP 策略

- [ ] **joint vs separate 混合策略** — 不是二选一，是 per-gate-type 选择。高重用度 → separate，低重用度 → joint
- [ ] **电路特征 → 最优混合比例** — 类似 λ_par 的做法，电路 → 最优调度策略

### 2.5 qubit priority

- [ ] **trap-aware priority** — 当前只看 layer index（1/(l+1)）。加 trap depth 权重 → 高重用且深阱的比特优先
- [ ] **态-aware priority** — 当前不看比特的量子态。初始态是 |0⟩ vs |1⟩ vs 叠加态 → 对串扰敏感性不同 → priority 应该考虑
- [ ] **对比实验** — ZAP default vs trap-aware vs state-aware vs 组合权重，fidelity 差异

### 2.6 idle_cost_alpha

- [ ] **α 参数扫描** — [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]，benchmark 全覆盖
- [ ] **硬件自适应 α** — α = f(f_tr, f_xtalk, T2) 的函数形式，不是固定值
- [ ] **α 灵敏度热力图** — f_tr × f_xtalk × T2 三维参数空间上的最优 α 分布

---

## 三、Fidelity 模型升级（Eq.4 → 更完整的物理模型）

- [ ] **五项 → N 项** — 当前五通道独立乘性。至少加：关联错误项（cosmic ray / leakage propagation）、多原子集体退相干项
- [ ] **非马尔可夫修正** — 当前假设指数衰减 exp(-t/T2)。真实 1/f 噪声 → stretched exponential 或高斯衰减。查文献标定
- [ ] **搬运保真度公式精细化** — f_tr = f(distance, velocity, trap_depth, heating_rate)，替代常数 0.999
- [ ] **校准感知编译接口** — fidelity model 的参数不从论文抄，从外部校准文件读（JSON），模拟"今天的硬件状态"
- [ ] **跨编译器 fidelity 等价性文档** — Enola/ZAC 各用自己的 fidelity 口径。你的 Eq.4 是统一口径——文档化：为什么同一个 fidelity 公式可以跨编译器用、哪些项是编译器无关的、哪些项有隐含的编译器假设

---

## 四、编译器鲁棒性（方向三）

- [ ] **参数不确定性的 Monte Carlo 传播** — 每个决策做 100 次 Monte Carlo，每次从硬件参数分布中采样。不只看最优 fidelity——看 fidelity 分布的均值和方差
- [ ] **鲁棒优化替代确定性优化** — AL solver 的目标从 `min(cost)` 改成 `min(max(cost))`——在所有可能的硬件参数下最坏情况最优
- [ ] **最坏情况 benchmark** — 对每个电路，找"硬件参数组合使 ZAP 的编译决策变成最差"的那个点
- [ ] **校准频率 vs 重编译频率的 trade-off** — 硬件参数漂移的典型时间尺度 vs 编译一次的时间开销 → 最优的重新校准/重编译策略

---

## 五、跨编译器对比（扩大实例覆盖）

### 5.1 Enola

- [ ] **Enola boundary 完善** — `instances/Enola/boundaries/B-enola-hardware.yaml` 已有，核查 cost_terms 是否和 Enola 论文的误差模型对齐
- [ ] **Enola 六桥等效映射** — Enola 没有 zone 架构，但同样面对 keep-vs-move（只不过"不搬"的代价变成了全局串扰而不是 zone 内串扰）。六座桥在 Enola 上分别对应什么
- [ ] **Enola vs ZAP fidelity breakdown 对比** — 同一 benchmark，同一 fidelity 口径，两张 fidelity breakdown 对比图

### 5.2 ZAC

- [ ] **ZAC boundary 创建** — `instances/ZAC/boundaries/` — ZAC 的 cost model：模拟退火的目标函数包含哪些项
- [ ] **ZAC 桥映射** — ZAC 用模拟退火全局优化 → 很多决策不是独立可替换的。桥的分析方法对全局优化器是否仍然有效
- [ ] **ZAC vs ZAP 编译时间 vs fidelity** — 验证 ZAP 的"单遍确定性碾压迭代"claim，同时标注 ZAC 在某些 benchmark 上是否 fidelity 更高

### 5.3 PowerMove

- [ ] **PowerMove boundary 创建** — PowerMove 含 surface code 编译 → fidelity model 需要扩展到逻辑错误率
- [ ] **PowerMove 的 zone/FTQC 迁移桥** — ZAP 的物理比特编译 → PowerMove 的逻辑比特编译，桥的类型可能从 tension 变成 supersede（旧机制被新机制替代）
- [ ] **单遍确定性哲学在 FTQC 下的可迁移性评估** — 这是胡孟军的下一步，你的分析可以直接给他提供参考

### 5.4 跨编译器不变量

- [ ] **四编译器统一 fidelity 对比表** — 同一套 benchmark，同一套 fidelity 口径，四个编译器
- [ ] **Rule of Three — 域级桥建表** — 三个编译器都面对同一对约束张力 → 从实例桥回溯建域级声明桥 BD-xxx。当前 `domain/bridge-declarations/` 是空的——填上第一座 BD
- [ ] **G(C) 跨编译器计算** — 不是跨域，是跨编译器。哪些桥的 resolve_fn 在四个编译器上都能用同一套逻辑？G(C) 接近 1.0 → 这个桥是物理决定的，不是架构决定的

---

## 六、物理保真度上界推导（方向四 — 申请最强钩子）

- [ ] **确定目标 benchmark** — 选 3 个代表性电路：QFT（蝶形长程）、QRAM（树形不规则）、Ising（规则近邻）
- [ ] **识别不可压缩的物理损耗** — 给定硬件参数，哪些 fidelity 损失是编译器无论如何都消除不了的：
  - 每个双比特门的最低时间 × 退相干
  - 量子信息在 AOD-SLM 间的最低转乘次数
  - 里德堡阻塞的最低泄漏概率
- [ ] **上界公式推导** — F_max(benchmark, hardware_params) = ? 不追求严格下界证明（那需要新物理），追求合理物理上界
- [ ] **gap = 上界 - ZAP 实际 fidelity** — 这是编译器还有多少优化空间的量化度量
- [ ] **gap 分解** — gap 的哪部分来自 ZAP 的物理简化（1.1-1.5 的五个缺陷），哪部分来自算法次优（单遍贪心 vs 全局最优）

---

## 七、Benchmark 体系扩展

- [ ] **不规则电路集** — QRAM (n=10,15,20)、VQC (n=8,12,16)、Multiplier (n=4,5,6)、QFT (已有)、GHZ (已有)
- [ ] **极端参数电路** — 超高重用度、极低重用度、全对全纠缠——测试编译器的极限行为
- [ ] **变规模扫描** — 同一电路类型，n=10→100，标度律测绘
- [ ] **混合电路** — QFT + QRAM 片段组合，模拟真实算法
- [ ] **FTQC 电路** — 如果 PowerMove 支持 → surface code 逻辑比特电路 → 测试 ZAP 哲学在逻辑层的迁移性

---

## 八、框架自身（用编译器分析倒逼框架改进）

- [ ] **新桥类型** — 1.2（阻塞概率）暴露的 trade-off 可能不属于已有的 7 种桥类型。如果需要新类型 → 加
- [ ] **约束耦合建模** — 1.1（搬运-退相干耦合）暴露了约束之间不是独立的。框架需要支持"约束之间的相互作用箭头"——当前 schema 不包含这个
- [ ] **boundary 参数从固定值→分布** — 方向三（鲁棒优化）要求 boundary 的 cost_terms 支持区间和分布，不只是点值
- [ ] **bridge 的物理驱动发现** — 1.3 和 1.4 发现的新桥不是从已有约束推导的——是从物理缺陷中"涌现"的。这恰好是 L1→L2：约束从物理边界条件中推导出新约束
- [ ] **check.py 规则精简化** — 当前 14 条规则校验没人读的 YAML。清理：只保留被实验脚本引用的规则
- [ ] **实验-YAML 绑定** — 实验脚本从 YAML 加载约束/边界/桥参数，而不是手写 Python 字典
- [ ] **instance-space 扩增** — `noise-sensitivity`（噪声灵敏度测试空间）、`scalability`（标度律测试空间）

---

## 九、申请材料

- [ ] **个人陈述/研究计划** — 四段叙事：我读懂了 ZAP → 我找到了决策边界（六桥数据）→ 我在 keep-vs-move 上做了改进（AL 软决策）→ 我想在你的组里做这些（物理缺陷测绘 + 保真度上界）
- [ ] **技术报告附录** — 六桥敏感性完整数据表、三编译器交叉验证详情、AL vs hard threshold 完整对比、参数扫描热力图
- [ ] **代码仓库** — README 30 秒能跑通、实验可复现、数据引用 commit hash
- [ ] **ZAP 深度解读** — `docs/papers/ZAP-paper-reading.md` 已有，精修后作为附件。"证明我读懂了"的直接证据

---

## 十、长线方向（申请里半句话带过，长期做铺垫）

- [ ] **多 zone 架构** — 不止一个纠缠区。物理上需要什么条件？编译器上调度复杂度怎么变？
- [ ] **多原子种类** — Rb vs Sr vs Yb — 不同物理参数（T2, f_tr, 阻塞半径）→ 最优编译策略差异
- [ ] **动态 zone — 编译器反向设计硬件** — zone 的大小/形状/位置由电路结构决定，不是固定两区
- [ ] **FTQC 编译** — ZAP 确定性单遍哲学在逻辑比特层的推广。物理比特编译 → 逻辑比特编译 → 魔术态工厂调度
- [ ] **时空调制** — 里德堡激光空间模式调制 → "软 zone"——不是物理隔离，是空间可编程的串扰管理
- [ ] **实时校准感知编译** — 编译期间硬件的校准数据在变 → 编译决策需要在编译中途根据最新校准数据调整

---

> 原则：
> - 做完一件划一件。新增补在末尾。
> - 每件事产出一个可核查的产物（数据表 / 图 / 代码 diff / 文档段落）。
> - 如果一件事只产出了"更深入的理解"但没有任何可核查产出 → 把它拆成更小的事。
> - 框架的改进是编译器分析的副产品，不是前提条件。先有发现，再改进框架去承载它。
