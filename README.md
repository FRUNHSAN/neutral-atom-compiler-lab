# neutral-atom-compiler-lab

> 中性原子量子编译器决策点分析。
> 测绘 ZAP（IEEE TQE 2026）的 6 个编译决策点，定位唯一高敏感性参数，keep-vs-move 硬阈值→联合优化。
> 中性原子量子编译器决策点分析——方法、实验、结论。

---

## 新手入口

| 你想… | 读这个 | 时间 |
|---|---|---|
| 了解中性原子量子计算 | [中性原子知识点结构树](docs/neutral-atom-knowledge-tree.md) | 15 分钟 |
| 看懂 ZAP 论文 | [ZAP 论文详解](application/02_ZAP论文详解.md) | 10 分钟 |
| 看核心实验和结论 | [实验报告](application/03_实验报告.md) | 10 分钟 |
| 看完整叙事 | [项目总述](application/01_项目总述.md) | 5 分钟 |
| 接手这个项目继续干 | [工作进度报告](HANDOFF.md) | 5 分钟 |
| 看还有什么能做 | [完整待做事项](ROADMAP.md) | 随意 |

---

## 定位

中性原子量子计算有一个独特优势——原子可以用光镊搬来搬去。但搬原子需要时间，搬的时候所有原子在退相干，搬错路线会撞车，搬太多会丢原子。**编译器的工作就是在这些物理约束之间做决策。**

ZAP（Zoned Architecture and Performant Compiler, IEEE TQE 2026）是目前该方向最先进的方案——分区架构 + 单遍确定性编译。本项目不修改 ZAP 源码，用 monkey-patch 替换它的全部 6 个决策点，回答一个问题：**哪些决策点值得优化，哪些已经够好了？**

**核心发现**：6 个决策点中 5 个已达 fidelity 平台期，只有 keep-vs-move（空闲比特留在纠缠区还是搬回存储区）存在结构性优化空间——硬阈值在 slot 紧约束下系统性失效（170 次违反），联合优化版本消除所有违反。

---

## 快速开始

```bash
# 1. 环境
python -m venv venv
source venv/Scripts/activate       # Windows Git Bash
# source venv/bin/activate         # macOS / Linux

# 2. 依赖
pip install -r requirements.txt

# 3. 框架自检
python framework/check.py .
# → PASS: 0 FAIL / 0 WARN / 12 FYI（含链完整性 + .stale.json 归档）

# 4. 核心实验（无需 ZAP 源码 — synthetic 模式）
python experiments/strategy_compare.py       # 硬阈值 vs AL 软决策
python experiments/bridge_swap.py            # 六桥 swap
python experiments/tight_slot_compare.py --stress  # 紧 slot 压力测试 (170→0, 确定性)
python experiments/cross_validate.py         # 三编译器 fidelity 验证

# 5. ZAP 复现（需要 baselines/ 中的 ZAP 源码）
python experiments/reproduce_zap.py --quick  # 5 个 benchmark，~2 秒

# 6. 生成申请图表
python experiments/figures.py                # → application/figures/ (5 PNGs)
```

---

## 方法

### 不改源码，改决策点

ZAP 的 6 个编译决策通过**架构 JSON monkey-patch** 注入——修改 ZAP 读入的配置参数，不触碰 ZAP 源码（前置承诺：`baselines/` 存在时自动激活）。每替换一个决策点，用统一的 fidelity 公式（Eq.4, 5 通道分解）测量影响。

### 桥：决策点的统一形式

每个编译决策被形式化为一座**桥（Bridge）**——一对物理约束之间的张力 + 消解策略：

| 桥 | 约束张力 | ZAP 默认 | 替代方案 | Δ Fidelity | 敏感性 |
|---|---|---|---|---|---|
| keep-vs-move | 串扰 vs 搬运+退相干 | hard_threshold Eq.15 | AL 联合优化 | 0 | **高** |
| parallel-vs-distance | 并行度 vs 搬运距离 | λ=1000 固定 | 电路自适应 | 0 | 低 |
| parking-displacement | 坑位质量 vs 搬运距离 | 1 site | 5 sites | -0.0001 | 中 |
| asap-strategy | stage 深度 vs 搬运频率 | separate | joint | 0 | 低 |
| qubit-priority | 重用频率 vs 距离 | 1/(l+1) | reuse-aware | 0 | 低 |
| idle-cost-alpha | 闲置代价 vs 搬运代价 | α=1.0 | α=2.0 | 0 | 低 |

**结论**：5/6 的桥在 TQE benchmark 尺度（10–30 比特）上已达 fidelity 平台期。仅 keep-vs-move 存在结构性优化空间——不是 fidelity 差异，而是 slot 约束违反。

### keep-vs-move：从硬阈值到联合优化

ZAP Eq.15 是 per-qubit 独立硬阈值（`if L_xtalk > L_tr + L_dec → move`），不考虑全局 slot 容量约束。

**AL 软决策**：连续权重 w∈[0,1] + 全局 slot 约束 Σ(1−w_i) ≤ slot_count → 增广拉格朗日联合求解：

| 场景 | hard_threshold | AL soft | 改善 |
|---|---|---|---|
| 宽松 slot (4 for 20q) | fidelity 0.80, 0 violation | fidelity 0.79, 0 violation | 无差异 |
| 紧 slot (3 for 20q) | **170 violations** | **0 violations** | 170→0 |

**AL 在常规场景不伤保真度，紧 slot 下消除所有约束违反。结构性修复，不是参数调优。**

---

## 优化方向

### 短期

1. **物理缺陷测绘**：ZAP fidelity 模型的 5 个过度简化——搬运-退相干耦合、里德堡阻塞概率性、f_tr 空间依赖性、SLM 阵列不均匀、串扰空间依赖
2. **跨编译器推广**：桥分析方法应用于 Enola/ZAC/PowerMove，提取编译器无关的物理编译上界
3. **三支冲突分析 × 编译器桥**：胡孟军老师的冲突分析理论（IEEE TFS 2026）为编译器决策提供形式化地基

### 长线

- 物理保真度上界推导
- 参数不确定性下的鲁棒编译
- 多 zone / 动态 zone / 多原子种类
- FTQC 逻辑比特编译

详见 [ROADMAP.md](ROADMAP.md)。

---

## 三编译器交叉验证

同一套 fidelity 公式验证三个编译器的内置仿真器：

| 编译器 | 架构 | 结果 |
|---|---|---|
| Enola (UCLA-VAST) | 单区，无 zone | 5/5 PASS |
| ZAC (UCLA-VAST, HPCA 2025) | zone，模拟退火迭代 | 6/6 PASS |
| ZAP (BAQIS, IEEE TQE 2026) | zone，单遍确定性 | 内置自洽 |

**意义**：fidelity 公式与三个独立编译器在 accounting 层面一致 → 所有桥 swap 度量可靠。

---

## 框架层

本项目是**约束式工程框架**在量子编译器域的实例。框架本身包含：

- **三元架构 (H, A, F, P)**：人定义约束 → AI 做语义推理 → 框架做结构检查。详见 [Doc 31](docs/papers/constraint-engineering-theory/31-三元架构：人-AI-框架协作的形式化.md)
- **Protocol 0-8**：AI 协作者的行为约束协议，从"文档优先"到"约束与求解器分离"。详见 [CLAUDE.md](CLAUDE.md)
- **推理链**：记录"为什么不那样做"的决策记录系统。公开链（`chains/`）git 追踪，私有链（`chains_private/`）仅本地。详见 [Doc 34](docs/papers/constraint-engineering-theory/34-推理链制作方法.md)
- **约束式结构论 (Σ, Φ, D, E)**：PLT、控制论、热力学等七套理论的共同骨架。详见 [Doc 29](docs/papers/constraint-engineering-theory/29-约束式结构论.md)

---

## 项目结构

```
neutral-atom-compiler-lab/
├── framework/              元层：域无关的元语言
│   ├── schema.py           Constraint / Boundary / Bridge 数据模型
│   ├── solver_adapter.py   SolverAdapter ABC + Solution
│   ├── io.py               YAML 加载 + 注册表
│   ├── check.py            ~30 条规则 (F/B/BD/BR/IS/D/S 组), 0 FAIL
│   ├── stale_snapshot.py   验证栈时间序列归档
│   └── tags.yaml           受控领域词汇表
│
├── domain/
│   ├── constraints/        10 条物理约束 (YAML, CI 金丝雀)
│   └── formulas/
│       └── fidelity.py     Eq.4 五通道 fidelity 模型（唯一正本）
│
├── instance-space/
│   └── tqe-benchmark/      TQE benchmark 实例空间 (protocol + ruler + declarations)
│
├── instances/
│   ├── ZAP/                1 边界 + 2 座桥 + AL solver adapter
│   ├── Enola/              1 边界
│   └── ZAC/                (待补)
│
├── experiments/
│   ├── strategy_compare.py     硬阈值 vs AL 软决策
│   ├── bridge_swap.py          六桥 swap (synthetic + live ZAP)
│   ├── tight_slot_compare.py   紧 slot 压力测试 (170→0)
│   ├── cross_validate.py       三编译器 fidelity 交叉验证
│   ├── lambda_par_swap.py      λ_par 参数扫描
│   ├── reproduce_zap.py        ZAP benchmark 复现
│   └── figures.py              申请材料 5 张图
│
├── .ai_reasoning/          推理链：index.yaml + chains/ (公开, git 追踪)
│
├── application/            申请材料包 (4 篇文档 + 5 张图)
│
├── docs/
│   ├── ZAP-paper-reading.md         ZAP 论文深度解读
│   ├── neutral-atom-knowledge-tree.md  中性原子知识结构树
│   ├── RESEARCH.md                  研究计划书
│   ├── SUMMARY.md                   工作总结
│   ├── papers/                      论文 + 文献
│   │   ├── constraint-engineering-theory/   约束工程论（Doc 00-34）
│   │   ├── quantum-primer/                  量子计算科普（8 篇）
│   │   ├── quantum-engineering/            量子工程六层（6 篇）
│   │   ├── quantum-glossary/               量子术语表（7 篇）
│   │   ├── bridge-three-dimensions.md      桥的三维分类
│   │   ├── framework-full-architecture.md  框架完整施工图
│   │   ├── domain-deploy-quantum-compiler.md 量子编译器域部署
│   │   └── ZAP*.pdf                 ZAP 原论文
│
├── baselines/              第三方编译器源码 (需自行 clone, gitignored)
├── CLAUDE.md               AI 协作者入口（Protocol 0-8 + 框架速查）
├── HANDOFF.md              工作进度报告（给接手者）
├── ROADMAP.md              完整待做事项
└── requirements.txt
```

---

## 依赖

- Python ≥ 3.10
- pyyaml ≥ 6.0（YAML 加载）
- matplotlib ≥ 3.8 + numpy ≥ 1.26（可视化）
- qiskit ≥ 2.0 + qiskit-qasm3-import ≥ 0.6 + tqdm（ZAP live 模式，可选）

ZAP 源码：`git clone https://github.com/BAQIS-Quantum/neutral-atom-compilation baselines/neutral-atom-compilation`

---

## License

MIT
