"""
OptGraph - Production-Ready Agent Orchestration Framework

Core components:
- MemoryState: State management with memory
- ParallelExecutor: Dependency-aware parallel execution
- CostTracker: Real-time cost monitoring and budget control
- OptGraph: LangGraph wrapper with optimizations
"""

__version__ = "0.4.0"

from optgraph.memory_state import MemoryState, compress_memory, get_context_with_memory
from optgraph.executor import DependencyAwareExecutor
from optgraph.cost_tracker import CostTracker, BudgetExceededError
from optgraph.parallel_executor import ParallelExecutor, Task
from optgraph.optgraph import OptGraph, patch_langgraph, unpatch_langgraph, is_patched
from optgraph.callbacks import (
    CostTrackingCallback,
    CostTrackedLLM,
    enable_cost_tracking,
    add_cost_tracking_callback,
)

__all__ = [
    "MemoryState",
    "compress_memory",
    "get_context_with_memory",
    "DependencyAwareExecutor",
    "CostTracker",
    "BudgetExceededError",
    "ParallelExecutor",
    "Task",
    "OptGraph",
    "patch_langgraph",
    "unpatch_langgraph",
    "is_patched",
    "CostTrackingCallback",
    "CostTrackedLLM",
    "enable_cost_tracking",
    "add_cost_tracking_callback",
]
