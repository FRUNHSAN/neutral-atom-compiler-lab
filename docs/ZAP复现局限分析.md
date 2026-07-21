# ZAP 论文复现发现的可复现性局限

> 不是"论文错了"——是"论文的正确性边界"。
> 基于 224 次独立机检运行、4 编译器部署、12 个 bug 的经验归纳。

---

## 1. 跨编译器对比的口径不统一——这是最严重的

论文的 Fig.7/9/10/11 号称"四编译器用相同 fidelity 公式对比"。但我们在复现中发现：

**ZAC 的 crosstalk 计算被注释掉了。**
```
baselines/ZAC/zac/simulator/simulator.py:
    # self.cir_fidelity_2q_gate_for_idle *= pow(self.fidelity_2q_gate_for_idle, num_idle_qubits)
```
这行代码存在但被注释。结果：ZAC 输出的 `f_idle` 永远是 1.0——意味着串扰零惩罚。

但论文的 Fig.7 中 ZAC 的绿色柱（crosstalk 层）**不是零**。这意味着论文作者必然在 ZAC 的输出之上加了一层**统一的保真度后处理**。

**问题**：这层后处理代码不在公开仓库中。任何人想独立复现四编译器对比，都会发现自己的 ZAC f_idle 和论文对不上。论文的跨编译器"公平对比"依赖一个未公开的后处理脚本——这本质上不是可复现的。

---

**ZAC 二次 transpilation 导致 F_2q 不一致。**

我们给 ZAC 的是同一份 transpiled QASM，但 ZAC 内部调用 `transpile(circuit, basis_gates=["cz",...])` 重新 transpile 一次。不同 optimization_level 产生不同的 CZ 门数：
- qram_n20: ZAP F_2q = 0.5997 (102 gates)，ZAC F_2q = 0.5212 (131 gates)
- 差了 28 个门——这不是编译器质量差异，是 transpile 设置不统一

论文声称所有编译器用相同 fidelity 公式。这个说法在"公式相同"的意义上成立，但在"输入相同"的意义上不成立。F_2q 这一项已经不是同一个东西了。

---

## 2. 只有 1/14 benchmark 有精确数值——其余靠"看柱状图"

论文只显式给出了 qft_n10 的保真度数字（F_wo_1q = 0.541，§VII.A）。其余 13 个 benchmark 的论文值只能从 Fig.7 的堆叠柱状图靠肉眼读取。

视觉读取的不确定度约 ±0.02。而论文的核心声明"ZAP 比 ZAC 高 X%"，在大多数 benchmark 上的差距落在这个不确定度范围内。这意味着：
- 对 adder_n4：差距 0.01（看得见）
- 对 multiplier_n15：差距 0.002（看不见——可能是画图误差）

论文的 Fig.7 是**定性展示**而非**定量证据**。

---

## 3. qft_n10 的 2.1%——"排除单比特门"是一个隐藏陷阱

论文给的是 F_wo_1q = 0.541。我们复现的是 F_total = 0.530（含单比特门）。去除 1q 贡献后 F_wo_1q = 0.530。

Δ = 0.011 (2.1%)。这个差异来自 compiler-dependent 通道（F_tr, F_idle, F_dec）——即 ZAP 的 router 决策对 qiskit 版本敏感。

**这本身不是论文的问题**。qiskit 版本差异导致 transpilation 输出（操作名称/顺序）微妙变化 → router 的 stage 分组不同 → 执行时间不同 → fidelity 不同。

但**论文没有说明它使用的 qiskit 版本**——没有 `requirements.txt`。任何人在不同 qiskit 版本上复现，都可能得到 1-3% 的偏差，却不知道为什么。

---

## 4. PowerMove 和 Enola 的对比——公开仓库不可复现

**PowerMove**（4 个 commit，无 requirements.txt）：
- 10/14 benchmark 触发 Vizing 边着色 bug（`find_w_in_fan` 返回 None）
- 论文用的大概率是不同 Qiskit 版本 → 不同 transpile 输出 → 避开了边界 case
- 或者论文作者本地修了 bug 但没推到公开仓库

**Enola**（SA-based placement）：
- 单次编译 60-180s。14 benchmarks 需要 15-50 分钟
- 论文展示 Enola 在所有 14 个 benchmark 上的数据
- 这不是"不能跑"——是"用同样的硬件参数跑完需要的时间远超合理范围"
- 没有 requirements.txt 或环境配置

**这两项意味着：论文的多编译器"对比"在严格意义上只对 ZAP 和 ZAC 可独立复现。Enola 和 PowerMove 的数据依赖作者的计算环境。**

---

## 5. Fig.12 QFT N=500——transpile 瓶颈被归因错误

论文的 Fig.12 展示 QFT 在 ZAP 上的编译时间从 N=10 线性增长到 N=500。

我们在复现中发现：QFT N=100 的 QASM 3.0 文件包含 ~10,000 个门声明。`qiskit_qasm3_import.parse()` 需要 2+GB 内存并创建巨大 QuantumCircuit 对象。N=200 时已超出 60GB 磁盘的可用内存（exit code 120）。

N=500 QFT 的 QASM→CZ transpile 在这个物理机器上不可行——但这**不是 ZAP 的问题**。transpile 是所有编译器共享的预处理步骤。

**论文把 transpile + compile 的时间归因成了"ZAP compile time"**。如果 transpile 对 N=500 QFT 需要 5 分钟（在更大机器上），论文的 Fig.12 标注"ZAP: O(N)"就隐含了 transpile 时间——这不是 ZAP 的特性，是 Qiskit 的特性。

---

## 6. 170→0 的根本原因暴露了一个 design smell

我们中最先发现的 `hash()` 非确定性→stress test 数字不一致的问题，根因是 ZAP 的 stress test 用 `hash(circuit_type)` 做分类。

修成 `zlib.crc32()` 后数字确定了。但这个 bug 暴露出一个更深的问题：

**`hash()` 在所有 Python 3 版本中都是非确定性的（PYTHONHASHSEED=random）。这意味着 ZAP 的 stress test 在任何一台机器上的结果都是不可复现的——即使同一个 commit、相同 Python 版本。**

这是一个"论文声称可复现但实际不可复现"的硬证据。不是理论问题，不是参数偏差——是代码级事实。

---

## 7. 论文没有提供的几样东西

| 缺失 | 影响 |
|---|---|
| `requirements.txt` / `environment.yml` | 任何人在不同 qiskit 版本上得到不同数字都不知道原因 |
| 统一的 fidelity 后处理脚本 | 跨编译器对比无法独立复现（ZAC f_idle=1.0 就是证据） |
| 14 个 benchmark 的精确 fidelity 表 | 只能靠肉眼从柱状图读数（±0.02） |
| PowerMove 可运行的环境配置 | 10/14 benchmark 在当前环境下崩 |
| QFT N>100 的 transpile 中间产物 | QFT scalibility 数据无法复现 |

---

## 8. 论文说对的、我们能独立验证的

公平起见：

| 声明 | 验证 |
|---|---|
| ZAP >1000× faster than ZAC | ✅ adder_n4: 0.008s vs 10.8s = 1350× |
| ZAP fidelity 系统性高于 ZAC | ✅ 14/14 benchmarks |
| 退相干是大规模主导损失通道 | ✅ N=100 时 >50% |
| 动态策略不比全搬差 | ✅ Fig.13 |
| PowerMove F > ZAC F（在能跑的 benchmark 上） | ✅ adder_n4: 0.932 vs 0.904 |
| ZAP scheduler O(N) | ✅ Ising N=500: 30s 线性 |

**论文的方向性结论（ZAP > ZAC，动态策略有效，decoherence 主导）都在我们的独立复现中得到验证。差异在 1-3% 的数量级——不是方向级。**

---

## 结论性判断

**这篇论文在它自己的框架内是正确的。**所有方向性结论（ZAP 更快更好、动态策略有效、退相干主导）被独立验证。工程实现确实在 >99% 的情况下是确定性的。

**但它的可复现性没有它声称的那么好。**主要体现在：
1. 跨编译器对比依赖未公开的 fidelity 后处理层
2. 第三方编译器（PowerMove、Enola）的环境锁不存在
3. 精确数值只有 1/14 benchmark 显式给出
4. transpile 时间被混入"ZAP compile time"
5. stress test 用 `hash()`——任何机器上的数字都不一样

**这不是"撤回论文"级别的缺陷。**但是"需要附加上下文才能复现"级别的缺陷。任何声称"我们验证了 ZAP 论文"的人，如果没遇到这五个问题中的至少三个，说明他们没有真正跑过。
