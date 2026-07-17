---
chain_id: 2026-07-17-hash-determinism-fix
title: "hash()→zlib.crc32：修复实验不可复现的确定性 bug"
layer: L1
ternary_owner: agent
tags: [bug, determinism, reproducibility, hash, experiment]
status: active
created: 2026-07-17
supersedes: []
superseded_by: []
reverted_by: ""
related: ["2026-07-17-yaml-ci-canary"]
files:
  constraints: []
  boundaries: []
  bridges: []
  code:
    - "experiments/strategy_compare.py"
    - "experiments/tight_slot_compare.py"
    - "instances/ZAP/adapter.py"
  experiments:
    - "experiments/tight_slot_compare.py"
    - "experiments/strategy_compare.py"
produces_invariants: []
produces_constraints: []
cross_domain: false
domains_verified: []
---

# Context

`tight_slot_compare.py` 和 `strategy_compare.py` 使用 `hash(circuit_type)` 生成随机种子。Python 3.3+ 默认 `PYTHONHASHSEED=random`——每次独立进程运行，`hash('qram')` 返回不同值。`seed=42` 形同虚设。

后果：申请材料的核心数字（168→0）每次运行不同——可能是 127、168、161、0。胡孟军 clone 仓库后跑出 0→0，邮件里的"结构性失效"主张瞬间变成数字对不上。

这直接违反项目自身铁律——"所有实验可复现——脚本参数化"（CLAUDE.md / Protocol 5：代码偏离文档原则）。

# Decision

**`hash(circuit_type)` → `zlib.crc32(circuit_type.encode())`。两文件各改一行。全仓库数字从 168 统一为 161（crc32 下的稳定 stress test 结果）。**

# Rationale

`zlib.crc32` 在标准库中，跨进程、跨平台、跨 Python 版本输出完全一致。`crc32('qram')` 永远返回 `3931628504`——无论什么 PYTHONHASHSEED。

修复后 stress test（slot=3, n_q=20, 70% prefer stay）稳定输出 `hard_threshold violations: 161, AL soft violations: 0`。三进程验证全部一致。

# Alternatives

- **用 `hashlib.md5`**：同样确定性，但需要 bytes→hex→int 转换链，不如 crc32 直接返回整数
- **用 `PYTHONHASHSEED=0` 环境变量**：修复了可复现性，但要求每个运行者在命令行加环境变量——README 变长、新人必然忘记。不可接受
- **用固定 seed 不用 circuit_type**：三个电路类型输出相同 cost matrix——失去了电路类型间的区分度。不可接受

# Evidence

- 独立进程三次运行：hash 输出分别为 `1672806350090476774`, `-4459704626103846564`, `5706214236424888944`
- crc32 三次输出：全部 `3931628504`
- 修复后 stress test 三进程验证：全部 `hard=161, soft=0`

# Future Guidance

- 永远不要在 `random.Random()` 种子里用 Python 内置 `hash()`。用 `zlib.crc32()` 或 `hashlib.md5()`
- 新实验脚本加确定性检查：同一脚本跑两次 → 输出必须逐字节相同
- 申请材料里的数字出现变更时 → 先确认是否由随机性导致 → 如果是，修代码 > 改文档

# Anti-Patterns

- 不要把"上次跑出来的数字"写进文档而不验证它是否稳定
- 不要假设 `hash()` 在独立进程间一致——它从 Python 3.3 起就是加盐的
- 不要用环境变量修复可复现性问题——代码必须是自包含的
