# -*- coding: utf-8 -*-
"""
Test error handling and edge cases

Tests what we didn't test before:
- Task failures
- Timeouts
- max_workers limits
"""

import asyncio
import time
from optgraph.parallel_executor import ParallelExecutor, Task


async def successful_task(name: str, duration: float) -> str:
    """A task that succeeds"""
    await asyncio.sleep(duration)
    return f"{name}_success"


async def failing_task(name: str) -> str:
    """A task that raises an exception"""
    await asyncio.sleep(0.1)
    raise ValueError(f"{name} failed intentionally")


async def timeout_task(name: str) -> str:
    """A task that never completes"""
    await asyncio.sleep(999)  # Sleep forever
    return f"{name}_completed"


async def test_partial_failure():
    """
    Test: Some tasks fail, others succeed
    Expected: Executor completes, failed tasks return Exception
    """
    print("=" * 70)
    print("Test 1: Partial Failure Handling")
    print("=" * 70)

    task1 = Task("success1", lambda: successful_task("task1", 1.0))
    task2 = Task("failure", lambda: failing_task("task2"))
    task3 = Task("success2", lambda: successful_task("task3", 1.0))

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3])
    elapsed = time.time() - start

    print(f"\nResults:")
    for task_id, result in results.items():
        if isinstance(result, Exception):
            print(f"  {task_id}: [FAILED] {type(result).__name__}: {result}")
        else:
            print(f"  {task_id}: {result}")

    print(f"\nTime: {elapsed:.2f}s")

    # Verify
    assert "success1" in results
    assert "failure" in results
    assert "success2" in results

    assert results["success1"] == "task1_success"
    assert isinstance(results["failure"], Exception)
    assert results["success2"] == "task3_success"

    print("\n[PASS] PASSED: Partial failures handled correctly")
    print("       Successful tasks completed, failed task returned Exception")
    return True


async def test_timeout():
    """
    Test: Task with timeout
    Expected: TimeoutError for slow task
    """
    print("\n" + "=" * 70)
    print("Test 2: Timeout Handling")
    print("=" * 70)

    # Normal task
    task1 = Task("fast", lambda: successful_task("fast", 0.5))

    # Task with 1s timeout, but needs 999s
    task2 = Task("slow", lambda: timeout_task("slow"), timeout=1.0)

    # Normal task
    task3 = Task("fast2", lambda: successful_task("fast2", 0.5))

    executor = ParallelExecutor()

    start = time.time()
    results = await executor.execute_batch([task1, task2, task3])
    elapsed = time.time() - start

    print(f"\nResults:")
    for task_id, result in results.items():
        if isinstance(result, Exception):
            print(f"  {task_id}: [TIMEOUT] {type(result).__name__}: {result}")
        else:
            print(f"  {task_id}: {result}")

    print(f"\nTime: {elapsed:.2f}s")
    print(f"Expected: ~1s (timeout triggers after 1s)")

    # Verify
    assert results["fast"] == "fast_success"
    assert isinstance(results["slow"], TimeoutError)
    assert results["fast2"] == "fast2_success"
    assert elapsed < 2.0, f"Should timeout quickly, but took {elapsed:.2f}s"

    print("\n[PASS] PASSED: Timeout handled correctly")
    print("       Slow task timed out, others completed normally")
    return True


async def test_max_workers():
    """
    Test: max_workers limits concurrency
    Expected: Only N tasks run concurrently
    """
    print("\n" + "=" * 70)
    print("Test 3: max_workers Concurrency Limit")
    print("=" * 70)

    # Track how many tasks are running concurrently
    running_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    async def tracked_task(name: str, duration: float) -> str:
        nonlocal running_count, max_concurrent

        async with lock:
            running_count += 1
            max_concurrent = max(max_concurrent, running_count)
            print(f"  [{time.strftime('%H:%M:%S')}] {name} started (concurrent: {running_count})")

        await asyncio.sleep(duration)

        async with lock:
            running_count -= 1
            print(f"  [{time.strftime('%H:%M:%S')}] {name} finished (concurrent: {running_count})")

        return f"{name}_done"

    # Create 6 tasks, but limit to 3 concurrent
    tasks = [
        Task(f"task{i}", lambda i=i: tracked_task(f"task{i}", 1.0))
        for i in range(1, 7)
    ]

    executor = ParallelExecutor(max_workers=3)

    print("\nRunning 6 tasks with max_workers=3...")
    print("Expected: At most 3 tasks running at the same time\n")

    start = time.time()
    results = await executor.execute_batch(tasks)
    elapsed = time.time() - start

    print(f"\nMax concurrent tasks: {max_concurrent}")
    print(f"Total time: {elapsed:.2f}s")
    print(f"Expected time: ~2s (6 tasks / 3 workers * 1s)")

    # Verify
    assert max_concurrent <= 3, f"max_workers=3 but saw {max_concurrent} concurrent"
    assert len(results) == 6
    assert all(not isinstance(r, Exception) for r in results.values())
    assert elapsed >= 1.9 and elapsed <= 2.5, f"Expected ~2s, got {elapsed:.2f}s"

    print("\n[PASS] PASSED: max_workers limit enforced")
    print(f"       Never exceeded {max_concurrent}/3 concurrent tasks")
    return True


async def test_all_tasks_fail():
    """
    Test: All tasks fail
    Expected: All results are Exceptions
    """
    print("\n" + "=" * 70)
    print("Test 4: All Tasks Fail")
    print("=" * 70)

    tasks = [
        Task(f"fail{i}", lambda i=i: failing_task(f"task{i}"))
        for i in range(1, 4)
    ]

    executor = ParallelExecutor()

    results = await executor.execute_batch(tasks)

    print(f"\nResults:")
    for task_id, result in results.items():
        print(f"  {task_id}: {type(result).__name__}: {result}")

    # Verify
    assert len(results) == 3
    assert all(isinstance(r, Exception) for r in results.values())

    print("\n[PASS] PASSED: All failures handled gracefully")
    print("       Executor completed even though all tasks failed")
    return True


async def test_mixed_errors_and_dependencies():
    """
    Test: Failure in a dependency chain
    Expected: Later tasks should still execute even if earlier ones fail
    """
    print("\n" + "=" * 70)
    print("Test 5: Failures in Dependency Chain")
    print("=" * 70)

    # task1 fails, but task2 and task3 don't depend on it
    task1 = Task("fail_task", lambda: failing_task("task1"),
                 reads=set(), writes={"data1"})

    task2 = Task("success_task", lambda: successful_task("task2", 1.0),
                 reads=set(), writes={"data2"})

    # task3 depends on task2 (not task1), should succeed
    task3 = Task("dependent_success", lambda: successful_task("task3", 1.0),
                 reads={"data2"}, writes={"data3"})

    executor = ParallelExecutor()

    results = await executor.execute_batch([task1, task2, task3])

    print(f"\nResults:")
    for task_id, result in results.items():
        if isinstance(result, Exception):
            print(f"  {task_id}: [FAILED] {result}")
        else:
            print(f"  {task_id}: {result}")

    # Verify
    assert isinstance(results["fail_task"], Exception)
    assert results["success_task"] == "task2_success"
    assert results["dependent_success"] == "task3_success"

    print("\n[PASS] PASSED: Dependencies work despite other failures")
    print("       task2 and task3 succeeded even though task1 failed")
    return True


async def main():
    """Run all error handling tests"""

    print("\n")
    print("=" * 70)
    print("ERROR HANDLING AND EDGE CASE TESTS")
    print("=" * 70)
    print("\nThese tests verify robustness:")
    print("- Partial task failures")
    print("- Timeout handling")
    print("- max_workers enforcement")
    print("- Complete failure scenarios")
    print("\n")

    results = []

    # Test 1: Partial failure
    try:
        success = await test_partial_failure()
        results.append(("Partial Failure", success))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Partial Failure", False))

    # Test 2: Timeout
    try:
        success = await test_timeout()
        results.append(("Timeout Handling", success))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Timeout Handling", False))

    # Test 3: max_workers
    try:
        success = await test_max_workers()
        results.append(("max_workers Limit", success))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("max_workers Limit", False))

    # Test 4: All fail
    try:
        success = await test_all_tasks_fail()
        results.append(("All Tasks Fail", success))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("All Tasks Fail", False))

    # Test 5: Mixed errors
    try:
        success = await test_mixed_errors_and_dependencies()
        results.append(("Mixed Errors", success))
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        results.append(("Mixed Errors", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, passed in results:
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        print(f"{name:<30} {status}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print("-" * 70)
    print(f"Total: {passed_count}/{total_count} passed")

    if passed_count == total_count:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("\nConclusion: Error handling is robust!")
    else:
        print(f"\n[WARN] {total_count - passed_count} test(s) failed")
        print("\nConclusion: Error handling needs work!")


if __name__ == "__main__":
    asyncio.run(main())
