"""
OptGraph - Production-Ready Agent Orchestration Framework

Core components:
- AdaptiveCheckpointSaver: Context compression
- DependencyAwareExecutor: Parallel execution
- CostTracker: Cost monitoring
"""

__version__ = "0.1.0"

from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.executor import DependencyAwareExecutor
from optgraph.cost_tracker import CostTracker

__all__ = [
    "AdaptiveCheckpointSaver",
    "DependencyAwareExecutor",
    "CostTracker",
]
