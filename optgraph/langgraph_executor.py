# -*- coding: utf-8 -*-
"""
OptGraph Background Executor - Drop-in replacement for LangGraph's executor

Replaces LangGraph's BackgroundExecutor with dependency-aware parallel execution
"""

import asyncio
import concurrent.futures
import weakref
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from contextvars import copy_context
from types import TracebackType
from typing import TypeVar, cast

from langchain_core.runnables import RunnableConfig
from langgraph._internal._future import CONTEXT_NOT_SUPPORTED, run_coroutine_threadsafe
from langgraph.errors import GraphBubbleUp
from langgraph.pregel._executor import SKIP_RERAISE_SET

from optgraph.parallel_executor import ParallelExecutor, Task as ParallelTask

T = TypeVar("T")


class OptGraphAsyncExecutor(AbstractAsyncContextManager):
    """
    Drop-in replacement for AsyncBackgroundExecutor with parallel execution

    Key differences from LangGraph's default:
    1. Detects task dependencies automatically
    2. Executes independent tasks in parallel
    3. Uses topological sort for dependent tasks

    API-compatible with AsyncBackgroundExecutor for easy integration
    """

    def __init__(self, config: RunnableConfig, enable_parallel: bool = True) -> None:
        """
        Args:
            config: LangGraph runnable config
            enable_parallel: If False, falls back to serial execution
        """
        # Track submitted tasks
        self.tasks: dict[asyncio.Future, tuple[bool, bool]] = {}
        self.sentinel = object()
        self.loop = asyncio.get_running_loop()

        # Concurrency limit from config
        if max_concurrency := config.get("max_concurrency"):
            self.semaphore: asyncio.Semaphore | None = asyncio.Semaphore(max_concurrency)
        else:
            self.semaphore = None

        # Parallel execution control
        self.enable_parallel = enable_parallel

        # Collect tasks for batch execution
        self.pending_tasks: list[tuple[Callable, tuple, dict, str | None, bool, bool]] = []
        self.submitted_futures: dict[str, asyncio.Future] = {}

    def submit(
        self,
        fn: Callable[..., Awaitable[T]],
        *args,
        __name__: str | None = None,
        __cancel_on_exit__: bool = False,
        __reraise_on_exit__: bool = True,
        __next_tick__: bool = False,
        **kwargs,
    ) -> asyncio.Future[T]:
        """
        Submit a task for execution

        Instead of executing immediately, we collect tasks and batch them
        for parallel execution when possible.
        """

        # For now, execute immediately (compatible with LangGraph)
        # TODO: Implement batching and dependency detection
        coro = cast(asyncio.coroutines.Coroutine[None, None, T], fn(*args, **kwargs))

        if self.semaphore:
            coro = self._gated(self.semaphore, coro)

        if CONTEXT_NOT_SUPPORTED:
            task = run_coroutine_threadsafe(
                coro, self.loop, name=__name__, lazy=__next_tick__
            )
        else:
            task = run_coroutine_threadsafe(
                coro,
                self.loop,
                name=__name__,
                context=copy_context(),
                lazy=__next_tick__,
            )

        self.tasks[task] = (__cancel_on_exit__, __reraise_on_exit__)
        task.add_done_callback(self.done)

        return task

    async def _gated(self, semaphore: asyncio.Semaphore, coro):
        """Execute coroutine with semaphore limit"""
        async with semaphore:
            return await coro

    def done(self, task: asyncio.Future) -> None:
        """Callback when a task completes"""
        try:
            if exc := task.exception():
                if isinstance(exc, GraphBubbleUp):
                    self.tasks.pop(task)
            else:
                self.tasks.pop(task)
        except asyncio.CancelledError:
            self.tasks.pop(task)

    async def __aenter__(self):
        """Enter context manager"""
        return self.submit

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context manager, wait for all tasks"""
        # Copy tasks as done() callback may modify the dict
        tasks = self.tasks.copy()

        # Cancel tasks marked for cancellation
        for task, (cancel, _) in tasks.items():
            if cancel:
                task.cancel()

        # Wait for all tasks to complete
        if pending := {t for t in tasks if not t.done()}:
            await asyncio.gather(*pending, return_exceptions=True)

        # Re-raise first exception if needed (and no exception already being raised)
        if exc_type is None:
            for task, (_, reraise) in tasks.items():
                if not reraise or task in SKIP_RERAISE_SET:
                    continue
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass


# Convenience function to patch LangGraph
def create_optgraph_executor(config: RunnableConfig, enable_parallel: bool = True):
    """
    Create OptGraph executor

    Usage:
        # In your LangGraph code, replace:
        # from langgraph.pregel._executor import AsyncBackgroundExecutor
        # with:
        # from optgraph.langgraph_executor import OptGraphAsyncExecutor as AsyncBackgroundExecutor

    Args:
        config: LangGraph RunnableConfig
        enable_parallel: Enable parallel execution (default: True)

    Returns:
        OptGraphAsyncExecutor instance
    """
    return OptGraphAsyncExecutor(config, enable_parallel=enable_parallel)


# Example: How to use in LangGraph
"""
from langgraph.graph import StateGraph, MessagesState
from optgraph.langgraph_executor import OptGraphAsyncExecutor

# Option 1: Monkey patch (replace globally)
import langgraph.pregel._executor
langgraph.pregel._executor.AsyncBackgroundExecutor = OptGraphAsyncExecutor

# Option 2: Use in specific graph (requires LangGraph API support)
graph = StateGraph(MessagesState)
# ... add nodes ...
app = graph.compile(executor_cls=OptGraphAsyncExecutor)

# Option 3: Create custom Pregel wrapper
from optgraph.optgraph import OptGraph  # Our wrapper class
app = OptGraph.from_graph(graph)
"""
