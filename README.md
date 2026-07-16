# neutral-atom-compiler-lab

> 中性原子量子编译器分析——约束式工程框架 × ZAP 范式边界测绘。
> 面向北京量子信息科学研究院 2026 年"量子青年人才储备计划"，目标导师：胡孟军。

## 一句话

不修改 ZAP（IEEE TQE 2026）源码，用 monkey-patch 替换全部 6 个决策点，在 3 类电路上完成基准对比；用同一 fidelity 公式交叉验证 Enola / ZAC / ZAP 三个编译器（11/11 PASS）。

**整个项目由约束式工程框架组织——四层架构，30 条自动化一致性检查规则。**

---

## 四层架构

```
framework/         元层：域无关的元语言
  schema / check / solver_adapter / io / tags

domain/            第1层：所有编译器共享
  constraints/       约束 — "应该是什么"（10 条 YAML）
  formulas/          公式结构 — 不是参数（fidelity.py）
  bridge-declarations/  域级桥声明 — "哪些约束之间有张力"（Rule of Three）

instance-space/    第2层：实例们共同生活的环境
  protocol.yaml      约定 + 尺子 — 最小存在条件
  declarations/      等效声明 — "谁跟谁比，差多少"

instances/         第3层：每个编译器私有的选择
  ZAP/  Enola/  ZAC/   边界 + 桥 + adapter
```

**尺子是 instance-space 的最小存在条件。** 没有尺子 = 场景描述，不是实例空间。

---

## 做了什么

### 六桥基准测试

| Bridge | 默认 | 替代 | 敏感性 |
|--------|------|------|--------|
| BR-keep-vs-move | hard_threshold | AL 软决策 | **高** |
| BR-parallel-vs-distance | λ=1000 | 电路自适应 | 无 |
| BR-parking-displacement | 1 site | 5 sites | 弱 |
| BR-asap-strategy | separate | joint | 无 |
| BR-qubit-priority | 1/(l+1) | reuse-aware | 无 |
| BR-idle-cost-alpha | α=1.0 | α∈[0.5,5.0] | 中 |

### 三编译器交叉验证

| 编译器 | 结果 | 关键发现 |
|--------|------|---------|
| Enola | 5/5 PASS | 无 zone → crosstalk=0.975 |
| ZAC | 6/6 PASS | zone → crosstalk=1.0 |
| ZAP | 内置一致性 | lookahead/always_move/always_stay |

### 约束一致性检查

```bash
$ python framework/check.py .
  PASS: 0 FAIL / 0 WARN / 11 FYI
```

---

## 快速开始

```bash
pip install pyyaml
python framework/check.py .                    # 约束一致性检查
python experiments/strategy_compare.py         # 硬阈值 vs AL 软决策
python experiments/bridge_swap.py              # 六桥 swap (synthetic)
python experiments/bridge_swap.py --benchmark qft_n10  # 六桥 swap (live ZAP)
```
