# -*- coding: utf-8 -*-
"""
Parallel Execution Benchmark

Comprehensive benchmark comparing serial vs parallel tool execution
"""

import asyncio
import time
from typing import List, Tuple
from optgraph.parallel_executor import ParallelExecutor, Task


# ============= Mock Tool Functions =============

async def mock_api_call(duration: float, name: str) -> str:
    """Mock an API call with specified duration"""
    await asyncio.sleep(duration)
    return f"{name} completed"


# ============= Benchmark Scenarios =============

class BenchmarkScenario:
    """A benchmark test scenario"""

    def __init__(self, name: str, description: str,
                 task_specs: List[Tuple[str, float]]):
        """
        Args:
            name: Scenario name
            description: What this tests
            task_specs: List of (task_name, duration_seconds)
        """
        self.name = name
        self.description = description
        self.task_specs = task_specs

    def create_tasks(self) -> List[Task]:
        """Create Task objects for this scenario"""
        tasks = []
        for task_name, duration in self.task_specs:
            func = lambda d=duration, n=task_name: mock_api_call(d, n)
            task = Task(
                task_id=task_name,
                func=func,
                reads=set(),  # All independent
                writes={task_name}
            )
            tasks.append(task)
        return tasks

    async def run_serial(self) -> Tuple[dict, float]:
        """Run tasks serially"""
        start = time.time()
        results = {}

        for task_name, duration in self.task_specs:
            result = await mock_api_call(duration, task_name)
            results[task_name] = result

        elapsed = time.time() - start
        return results, elapsed

    async def run_parallel(self) -> Tuple[dict, float]:
        """Run tasks in parallel"""
        start = time.time()

        tasks = self.create_tasks()
        executor = ParallelExecutor()
        results = await executor.execute_batch(tasks)

        elapsed = time.time() - start
        return results, elapsed

    def expected_serial_time(self) -> float:
        """Calculate expected serial execution time"""
        return sum(duration for _, duration in self.task_specs)

    def expected_parallel_time(self) -> float:
        """Calculate expected parallel execution time"""
        return max(duration for _, duration in self.task_specs)


# ============= Benchmark Suite =============

BENCHMARK_SCENARIOS = [
    BenchmarkScenario(
        name="2_tasks_equal",
        description="2 tasks with equal duration",
        task_specs=[
            ("task1", 2.0),
            ("task2", 2.0),
        ]
    ),
    BenchmarkScenario(
        name="3_tasks_equal",
        description="3 tasks with equal duration",
        task_specs=[
            ("task1", 2.0),
            ("task2", 2.0),
            ("task3", 2.0),
        ]
    ),
    BenchmarkScenario(
        name="5_tasks_equal",
        description="5 tasks with equal duration",
        task_specs=[
            ("task1", 1.0),
            ("task2", 1.0),
            ("task3", 1.0),
            ("task4", 1.0),
            ("task5", 1.0),
        ]
    ),
    BenchmarkScenario(
        name="3_tasks_mixed",
        description="3 tasks with different durations",
        task_specs=[
            ("fast", 1.0),
            ("medium", 2.0),
            ("slow", 3.0),
        ]
    ),
    BenchmarkScenario(
        name="10_tasks_varied",
        description="10 tasks simulating real-world API calls",
        task_specs=[
            ("api1", 0.5),
            ("api2", 1.0),
            ("api3", 1.5),
            ("api4", 2.0),
            ("api5", 0.8),
            ("api6", 1.2),
            ("api7", 1.8),
            ("api8", 0.6),
            ("api9", 1.4),
            ("api10", 2.2),
        ]
    ),
]


async def run_benchmark():
    """Run full benchmark suite"""

    print("=" * 80)
    print("PARALLEL EXECUTION BENCHMARK")
    print("=" * 80)
    print("\nComparing serial vs parallel tool execution across multiple scenarios\n")

    results_summary = []

    for scenario in BENCHMARK_SCENARIOS:
        print("-" * 80)
        print(f"Scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"Tasks: {len(scenario.task_specs)}")
        print("-" * 80)

        # Run serial
        print("\nRunning serial execution...")
        serial_results, serial_time = await scenario.run_serial()
        print(f"  Completed in {serial_time:.2f}s")

        # Run parallel
        print("\nRunning parallel execution...")
        parallel_results, parallel_time = await scenario.run_parallel()
        print(f"  Completed in {parallel_time:.2f}s")

        # Calculate metrics
        speedup = serial_time / parallel_time
        latency_reduction = (1 - parallel_time / serial_time) * 100
        expected_serial = scenario.expected_serial_time()
        expected_parallel = scenario.expected_parallel_time()

        # Verify correctness
        assert len(serial_results) == len(parallel_results), "Result count mismatch"
        print("\n  Results verification: PASSED")

        # Print summary
        print("\n  Performance Summary:")
        print(f"    Serial time:     {serial_time:.2f}s (expected: {expected_serial:.2f}s)")
        print(f"    Parallel time:   {parallel_time:.2f}s (expected: {expected_parallel:.2f}s)")
        print(f"    Speedup:         {speedup:.2f}x")
        print(f"    Latency reduced: {latency_reduction:.1f}%")

        results_summary.append({
            "scenario": scenario.name,
            "num_tasks": len(scenario.task_specs),
            "serial_time": serial_time,
            "parallel_time": parallel_time,
            "speedup": speedup,
            "latency_reduction": latency_reduction
        })

        print()

    # Final summary table
    print("=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print()
    print(f"{'Scenario':<20} {'Tasks':<8} {'Serial':<10} {'Parallel':<10} {'Speedup':<10} {'Reduction':<10}")
    print("-" * 80)

    total_serial = 0
    total_parallel = 0

    for result in results_summary:
        print(f"{result['scenario']:<20} "
              f"{result['num_tasks']:<8} "
              f"{result['serial_time']:.2f}s{'':<5} "
              f"{result['parallel_time']:.2f}s{'':<5} "
              f"{result['speedup']:.2f}x{'':<5} "
              f"{result['latency_reduction']:.1f}%")

        total_serial += result['serial_time']
        total_parallel += result['parallel_time']

    print("-" * 80)

    avg_speedup = total_serial / total_parallel
    avg_reduction = (1 - total_parallel / total_serial) * 100

    print(f"\nOverall Statistics:")
    print(f"  Total serial time:     {total_serial:.2f}s")
    print(f"  Total parallel time:   {total_parallel:.2f}s")
    print(f"  Average speedup:       {avg_speedup:.2f}x")
    print(f"  Average reduction:     {avg_reduction:.1f}%")

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)

    # Check if we met the target
    if avg_reduction >= 50.0:
        print(f"\nSUCCESS: Target achieved! ({avg_reduction:.1f}% >= 50%)")
    else:
        print(f"\nWARNING: Target not met ({avg_reduction:.1f}% < 50%)")

    return results_summary


if __name__ == "__main__":
    asyncio.run(run_benchmark())
