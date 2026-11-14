"""
OptGraph - Production-Ready Agent Orchestration Framework

Core components:
- MemoryState: State management with memory
- DependencyAwareExecutor: Parallel execution
- CostTracker: Cost monitoring
"""

__version__ = "0.2.0"

from optgraph.memory_state import MemoryState, compress_memory, get_context_with_memory
from optgraph.executor import DependencyAwareExecutor
from optgraph.cost_tracker import CostTracker

__all__ = [
    "MemoryState",
    "compress_memory",
    "get_context_with_memory",
    "DependencyAwareExecutor",
    "CostTracker",
]
