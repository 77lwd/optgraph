# -*- coding: utf-8 -*-
"""
OptGraph Parallel Executor

Core implementation of dependency-aware parallel execution
"""

import asyncio
from typing import List, Dict, Set, Any, Callable
from collections import defaultdict


class Task:
    """Task representation (simplified for now)"""

    def __init__(self, task_id: str, func: Callable,
                 reads: Set[str] = None, writes: Set[str] = None,
                 timeout: float = None):
        """
        Args:
            task_id: Unique task identifier
            func: Async function to execute
            reads: Set of channels this task reads from
            writes: Set of channels this task writes to
            timeout: Optional timeout in seconds (None = no timeout)
        """
        self.id = task_id
        self.func = func
        self.reads = reads or set()
        self.writes = writes or set()
        self.timeout = timeout

    async def execute(self) -> Any:
        """Execute the task with optional timeout"""
        if self.timeout:
            try:
                return await asyncio.wait_for(self.func(), timeout=self.timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Task {self.id} exceeded timeout of {self.timeout}s")
        else:
            return await self.func()

    def __repr__(self):
        return f"Task({self.id})"


class ParallelExecutor:
    """Dependency-aware parallel task executor"""

    def __init__(self, max_workers: int = None):
        """
        Args:
            max_workers: Maximum concurrent tasks (None = unlimited)
        """
        self.max_workers = max_workers

    async def execute_batch(self, tasks: List[Task]) -> Dict[str, Any]:
        """
        Execute tasks with dependency detection and parallel execution

        Args:
            tasks: List of tasks to execute

        Returns:
            Dict mapping task_id to result
        """
        if not tasks:
            return {}

        # Step 1: Build dependency graph
        dep_graph = self._build_dependency_graph(tasks)

        # Step 2: Topological sort to get execution levels
        levels = self._topological_sort(tasks, dep_graph)

        # Step 3: Execute level by level
        all_results = {}

        for level_idx, level in enumerate(levels):
            print(f"Executing level {level_idx}: {[t.id for t in level]}")

            # Execute all tasks in this level concurrently
            level_results = await self._execute_level(level)

            # Collect results
            for task, result in zip(level, level_results):
                all_results[task.id] = result

        return all_results

    def _build_dependency_graph(self, tasks: List[Task]) -> Dict[Task, List[Task]]:
        """
        Build dependency graph: task -> list of tasks it depends on

        Dependency rule:
        Task A depends on Task B if:
        - A reads from a channel that B writes to

        Args:
            tasks: List of tasks

        Returns:
            Dict: {task: [dependencies]}
        """
        graph = {task: [] for task in tasks}

        for task_a in tasks:
            for task_b in tasks:
                if task_a != task_b:
                    # Check if task_a depends on task_b
                    # task_a.reads ∩ task_b.writes ≠ ∅
                    if task_a.reads & task_b.writes:
                        graph[task_a].append(task_b)

        return graph

    def _topological_sort(self, tasks: List[Task],
                         dep_graph: Dict[Task, List[Task]]) -> List[List[Task]]:
        """
        Topological sort using Kahn's algorithm

        Returns tasks grouped by execution levels:
        - Level 0: tasks with no dependencies (can run first)
        - Level 1: tasks that depend only on level 0
        - Level N: tasks that depend on levels 0..N-1

        Args:
            tasks: List of all tasks
            dep_graph: Dependency graph

        Returns:
            List of levels, each level is a list of tasks that can run in parallel
        """
        # Calculate in-degree (number of dependencies) for each task
        in_degree = {task: len(deps) for task, deps in dep_graph.items()}

        levels = []

        while in_degree:
            # Find all tasks with in-degree 0 (no dependencies)
            current_level = [task for task, degree in in_degree.items() if degree == 0]

            if not current_level:
                # Circular dependency detected
                remaining = list(in_degree.keys())
                raise ValueError(f"Circular dependency detected among tasks: {remaining}")

            levels.append(current_level)

            # Remove current level tasks and update in-degrees
            for task in current_level:
                del in_degree[task]

                # Reduce in-degree for tasks that depended on this one
                for other_task in in_degree.keys():
                    if task in dep_graph[other_task]:
                        in_degree[other_task] -= 1

        return levels

    async def _execute_level(self, tasks: List[Task]) -> List[Any]:
        """
        Execute all tasks in a level concurrently

        Args:
            tasks: List of tasks to execute in parallel

        Returns:
            List of results in the same order as tasks
            For failed tasks, returns Exception object instead of result
        """
        if self.max_workers and len(tasks) > self.max_workers:
            # Execute in batches if max_workers is set
            return await self._execute_with_limit(tasks)
        else:
            # Execute all tasks concurrently
            # return_exceptions=True: failed tasks return Exception, not raise
            return await asyncio.gather(*[task.execute() for task in tasks],
                                       return_exceptions=True)

    async def _execute_with_limit(self, tasks: List[Task]) -> List[Any]:
        """
        Execute tasks with concurrency limit

        Args:
            tasks: Tasks to execute

        Returns:
            List of results (or Exceptions for failed tasks)
        """
        semaphore = asyncio.Semaphore(self.max_workers)

        async def limited_execute(task):
            async with semaphore:
                return await task.execute()

        return await asyncio.gather(*[limited_execute(task) for task in tasks],
                                   return_exceptions=True)


# Example usage and tests
async def demo():
    """Demo of parallel execution with dependencies"""
    import time

    # Define some mock async functions
    async def fetch_weather(city):
        await asyncio.sleep(2)
        return f"{city}: 25°C, Sunny"

    async def fetch_news(topic):
        await asyncio.sleep(3)
        return f"Latest {topic} news"

    async def summarize(weather, news):
        await asyncio.sleep(1)
        return f"Summary: {weather}, {news}"

    # Scenario 1: Independent tasks (can run in parallel)
    print("\n=== Scenario 1: Independent Tasks ===")

    task1 = Task("weather_beijing", lambda: fetch_weather("Beijing"),
                 reads=set(), writes={"weather_beijing"})
    task2 = Task("weather_shanghai", lambda: fetch_weather("Shanghai"),
                 reads=set(), writes={"weather_shanghai"})
    task3 = Task("news_tech", lambda: fetch_news("Tech"),
                 reads=set(), writes={"news_tech"})

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3])
    elapsed = time.time() - start

    print(f"\nResults: {results}")
    print(f"Time: {elapsed:.2f}s (expected ~3s, max of all tasks)")

    # Scenario 2: Tasks with dependencies
    print("\n\n=== Scenario 2: Tasks with Dependencies ===")

    task1 = Task("weather", lambda: fetch_weather("Beijing"),
                 reads=set(), writes={"weather_data"})
    task2 = Task("news", lambda: fetch_news("Tech"),
                 reads=set(), writes={"news_data"})
    task3 = Task("summary", lambda: summarize("weather", "news"),
                 reads={"weather_data", "news_data"}, writes={"summary"})

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3])
    elapsed = time.time() - start

    print(f"\nResults: {results}")
    print(f"Time: {elapsed:.2f}s (expected ~4s: max(2,3) + 1)")


if __name__ == "__main__":
    asyncio.run(demo())
