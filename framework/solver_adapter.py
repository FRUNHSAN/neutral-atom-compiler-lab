"""
solver_adapter.py — 可插拔求解器接口。

当桥的 coupled=true 时，决策不是一个逐元素比较，而是一个联合优化问题。
SolverAdapter 定义了外部求解器的统一接口。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Solution:
    """求解器返回的统一结果。"""
    decisions: dict[str, int] = field(default_factory=dict)
    converged: bool = False
    elapsed_ms: float = 0.0
    objective_value: float = 0.0
    metadata: dict = field(default_factory=dict)


class SolverAdapter(ABC):
    """可插拔求解器抽象基类。

    每个耦合桥对应一个域特定的 adapter 实例。
    adapter 实现桥的 solve 逻辑。
    """

    @abstractmethod
    def solve(
        self,
        bridge_id: str,
        cost_matrix: dict,
        physical_constraints: dict | None = None,
        initial_guess: dict | None = None,
        timeout_ms: int = 50,
    ) -> Solution:
        """求解耦合桥决策。

        Args:
            bridge_id: 桥 ID
            cost_matrix: {element_id: {cost_term: value}}
            physical_constraints: 物理约束参数
            initial_guess: 前一阶段决策（warm start）
            timeout_ms: 超时阈值
        """
        ...
