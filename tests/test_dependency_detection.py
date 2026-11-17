# -*- coding: utf-8 -*-
"""
Test dependency detection and topological sort

This tests what we DIDN'T test in the main benchmark
"""

import asyncio
import time
from optgraph.parallel_executor import ParallelExecutor, Task


async def mock_task(name: str, duration: float) -> str:
    """Mock async task"""
    print(f"  [{time.strftime('%H:%M:%S')}] Start {name}")
    await asyncio.sleep(duration)
    print(f"  [{time.strftime('%H:%M:%S')}] Finish {name}")
    return f"{name}_result"


async def test_dependency_chain():
    """
    Test: task1 -> task2 -> task3 (must be serial)

    Expected:
    - Level 0: [task1]
    - Level 1: [task2]  (waits for task1)
    - Level 2: [task3]  (waits for task2)

    Total time: 1 + 1 + 1 = 3 seconds
    """
    print("=" * 70)
    print("Test 1: Dependency Chain (task1 -> task2 -> task3)")
    print("=" * 70)

    task1 = Task(
        task_id="task1",
        func=lambda: mock_task("task1", 1.0),
        reads=set(),
        writes={"data1"}
    )

    task2 = Task(
        task_id="task2",
        func=lambda: mock_task("task2", 1.0),
        reads={"data1"},  # depends on task1
        writes={"data2"}
    )

    task3 = Task(
        task_id="task3",
        func=lambda: mock_task("task3", 1.0),
        reads={"data2"},  # depends on task2
        writes={"data3"}
    )

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3])
    elapsed = time.time() - start

    print(f"\nResults: {results}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Expected: ~3s (serial: 1+1+1)")

    # Verify
    assert elapsed >= 2.9 and elapsed <= 3.2, f"Expected ~3s, got {elapsed:.2f}s"
    print("[PASS] PASSED: Tasks executed serially as expected")

    return elapsed


async def test_diamond_dependency():
    """
    Test: Diamond dependency

         task1
        /     \\
      task2   task3
        \\     /
         task4

    Expected:
    - Level 0: [task1]
    - Level 1: [task2, task3]  (parallel, both depend on task1)
    - Level 2: [task4]         (depends on both task2 and task3)

    Total time: 1 + max(1,1) + 1 = 3 seconds
    """
    print("\n" + "=" * 70)
    print("Test 2: Diamond Dependency")
    print("=" * 70)

    task1 = Task(
        task_id="task1",
        func=lambda: mock_task("task1", 1.0),
        reads=set(),
        writes={"data1"}
    )

    task2 = Task(
        task_id="task2",
        func=lambda: mock_task("task2", 1.0),
        reads={"data1"},
        writes={"data2"}
    )

    task3 = Task(
        task_id="task3",
        func=lambda: mock_task("task3", 1.0),
        reads={"data1"},
        writes={"data3"}
    )

    task4 = Task(
        task_id="task4",
        func=lambda: mock_task("task4", 1.0),
        reads={"data2", "data3"},  # depends on both task2 and task3
        writes={"data4"}
    )

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3, task4])
    elapsed = time.time() - start

    print(f"\nResults: {results}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Expected: ~3s (1 + max(1,1) + 1)")

    # Verify
    assert elapsed >= 2.9 and elapsed <= 3.2, f"Expected ~3s, got {elapsed:.2f}s"
    print("[PASS] PASSED: Diamond dependency handled correctly")

    return elapsed


async def test_circular_dependency():
    """
    Test: Circular dependency (should raise error)

    task1 -> task2 -> task1 (circular!)

    Expected: ValueError("Circular dependency detected")
    """
    print("\n" + "=" * 70)
    print("Test 3: Circular Dependency Detection")
    print("=" * 70)

    task1 = Task(
        task_id="task1",
        func=lambda: mock_task("task1", 1.0),
        reads={"data2"},  # depends on task2
        writes={"data1"}
    )

    task2 = Task(
        task_id="task2",
        func=lambda: mock_task("task2", 1.0),
        reads={"data1"},  # depends on task1 -> CIRCULAR!
        writes={"data2"}
    )

    executor = ParallelExecutor()

    try:
        results = await executor.execute_batch([task1, task2])
        print("[FAIL] FAILED: Should have raised ValueError for circular dependency")
        return False
    except ValueError as e:
        print(f"[PASS] PASSED: Correctly detected circular dependency")
        print(f"   Error message: {e}")
        return True


async def test_mixed_dependencies():
    """
    Test: Mix of independent and dependent tasks

    task1 (independent) \\
    task2 (independent)  -> task4 (depends on 1,2)
    task3 (independent) /

    Expected:
    - Level 0: [task1, task2, task3] (parallel)
    - Level 1: [task4] (waits for all)

    Total time: max(1,1,2) + 1 = 3 seconds
    """
    print("\n" + "=" * 70)
    print("Test 4: Mixed Dependencies")
    print("=" * 70)

    task1 = Task(
        task_id="task1",
        func=lambda: mock_task("task1", 1.0),
        reads=set(),
        writes={"data1"}
    )

    task2 = Task(
        task_id="task2",
        func=lambda: mock_task("task2", 1.0),
        reads=set(),
        writes={"data2"}
    )

    task3 = Task(
        task_id="task3",
        func=lambda: mock_task("task3", 2.0),  # Slowest
        reads=set(),
        writes={"data3"}
    )

    task4 = Task(
        task_id="task4",
        func=lambda: mock_task("task4", 1.0),
        reads={"data1", "data2", "data3"},  # depends on all
        writes={"data4"}
    )

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3, task4])
    elapsed = time.time() - start

    print(f"\nResults: {results}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Expected: ~3s (max(1,1,2) + 1)")

    # Verify
    assert elapsed >= 2.9 and elapsed <= 3.2, f"Expected ~3s, got {elapsed:.2f}s"
    print("[PASS] PASSED: Mixed dependencies handled correctly")

    return elapsed


async def main():
    """Run all dependency tests"""

    print("\n")
    print("=" * 70)
    print("DEPENDENCY DETECTION TESTS")
    print("=" * 70)
    print("\nThese tests verify what the main benchmark DIDN'T test:")
    print("- Dependency detection accuracy")
    print("- Topological sort correctness")
    print("- Circular dependency detection")
    print("\n")

    results = []

    # Test 1: Chain
    try:
        elapsed = await test_dependency_chain()
        results.append(("Dependency Chain", True, elapsed))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Dependency Chain", False, 0))

    # Test 2: Diamond
    try:
        elapsed = await test_diamond_dependency()
        results.append(("Diamond Dependency", True, elapsed))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Diamond Dependency", False, 0))

    # Test 3: Circular
    try:
        success = await test_circular_dependency()
        results.append(("Circular Detection", success, 0))
    except Exception as e:
        print(f"[FAIL] FAILED: Unexpected error: {e}")
        results.append(("Circular Detection", False, 0))

    # Test 4: Mixed
    try:
        elapsed = await test_mixed_dependencies()
        results.append(("Mixed Dependencies", True, elapsed))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Mixed Dependencies", False, 0))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, passed, elapsed in results:
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        time_str = f"({elapsed:.2f}s)" if elapsed > 0 else ""
        print(f"{name:<25} {status} {time_str}")

    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)

    print("-" * 70)
    print(f"Total: {passed_count}/{total_count} passed")

    if passed_count == total_count:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("\nConclusion: Dependency detection works correctly!")
    else:
        print(f"\n[WARN]  {total_count - passed_count} test(s) failed")
        print("\nConclusion: There are bugs in dependency handling!")


if __name__ == "__main__":
    asyncio.run(main())
