# -*- coding: utf-8 -*-
"""
Test Cost Tracking functionality

Tests:
1. Cost calculation accuracy
2. Database recording
3. Budget enforcement
4. Statistics queries
5. Budget exceeded error
"""

import os
import time
from optgraph.cost_tracker import CostTracker, BudgetExceededError, PRICING


def test_cost_calculation():
    """Test cost calculation accuracy"""
    print("=" * 70)
    print("Test 1: Cost Calculation")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")  # In-memory DB for testing

    # Test GPT-4
    cost = tracker._calculate_cost("gpt-4", 1000, 500)
    expected_input = (1000 / 1000) * PRICING["gpt-4"]["input"]
    expected_output = (500 / 1000) * PRICING["gpt-4"]["output"]
    expected_total = expected_input + expected_output

    print(f"\nGPT-4 (1000 input, 500 output tokens):")
    print(f"  Input cost:  ${cost['input_cost']:.4f} (expected: ${expected_input:.4f})")
    print(f"  Output cost: ${cost['output_cost']:.4f} (expected: ${expected_output:.4f})")
    print(f"  Total cost:  ${cost['total_cost']:.4f} (expected: ${expected_total:.4f})")

    assert abs(cost['input_cost'] - expected_input) < 0.0001
    assert abs(cost['output_cost'] - expected_output) < 0.0001
    assert abs(cost['total_cost'] - expected_total) < 0.0001

    # Test Claude-3 Opus
    cost = tracker._calculate_cost("claude-3-opus", 2000, 1000)
    expected_input = (2000 / 1000) * PRICING["claude-3-opus"]["input"]
    expected_output = (1000 / 1000) * PRICING["claude-3-opus"]["output"]
    expected_total = expected_input + expected_output

    print(f"\nClaude-3 Opus (2000 input, 1000 output tokens):")
    print(f"  Input cost:  ${cost['input_cost']:.4f} (expected: ${expected_input:.4f})")
    print(f"  Output cost: ${cost['output_cost']:.4f} (expected: ${expected_output:.4f})")
    print(f"  Total cost:  ${cost['total_cost']:.4f} (expected: ${expected_total:.4f})")

    assert abs(cost['input_cost'] - expected_input) < 0.0001
    assert abs(cost['output_cost'] - expected_output) < 0.0001
    assert abs(cost['total_cost'] - expected_total) < 0.0001

    print("\n[PASS] Cost calculation is accurate")
    return True


def test_logging():
    """Test logging LLM calls"""
    print("\n" + "=" * 70)
    print("Test 2: Logging LLM Calls")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Log a call
    result = tracker.log_call(
        model="gpt-4",
        input_tokens=1000,
        output_tokens=500,
        thread_id="thread_123",
        user_id="user_456",
        node_name="agent",
        purpose="test",
    )

    print(f"\nLogged call:")
    print(f"  Call ID: {result['call_id']}")
    print(f"  Cost: ${result['cost']:.4f}")
    print(f"  Budget status: {result['budget_status']}")

    # Verify it was recorded
    stats = tracker.get_stats()
    print(f"\nDatabase stats:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")

    assert stats['total_calls'] == 1
    assert stats['total_input_tokens'] == 1000
    assert stats['total_output_tokens'] == 500
    assert stats['total_tokens'] == 1500

    print("\n[PASS] Logging works correctly")
    return True


def test_budget_check():
    """Test budget checking"""
    print("\n" + "=" * 70)
    print("Test 3: Budget Checking")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Set budget
    tracker.set_budget(limit=1.0, scope="global")
    print("\nSet budget: $1.00")

    # Log some calls (should be within budget)
    for i in range(5):
        tracker.log_call("gpt-3.5-turbo", 1000, 500, thread_id=f"thread_{i}")

    budget_status = tracker.check_budget()
    print(f"\nAfter 5 calls:")
    print(f"  Current spend: ${budget_status['current_spend']:.4f}")
    print(f"  Budget limit: ${budget_status['budget_limit']:.2f}")
    print(f"  Usage: {budget_status['usage_percent']:.1f}%")
    print(f"  Within budget: {budget_status['within_budget']}")
    print(f"  Warning: {budget_status['warning']}")

    assert budget_status['within_budget'] == True

    print("\n[PASS] Budget check works correctly")
    return True


def test_budget_exceeded():
    """Test budget exceeded error"""
    print("\n" + "=" * 70)
    print("Test 4: Budget Exceeded Error")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Set a very low budget
    tracker.set_budget(limit=0.01, scope="global")
    print("\nSet budget: $0.01 (very low)")

    # Log a cheap call (should succeed)
    tracker.log_call("gpt-3.5-turbo", 100, 50)
    print("First call: Success (within budget)")

    # Try to log an expensive call (should fail)
    try:
        tracker.log_call("gpt-4", 5000, 5000)
        print("[FAIL] Should have raised BudgetExceededError")
        return False
    except BudgetExceededError as e:
        print(f"Second call: Correctly raised BudgetExceededError")
        print(f"  Error message: {e}")

    print("\n[PASS] Budget exceeded error works correctly")
    return True


def test_statistics():
    """Test statistics queries"""
    print("\n" + "=" * 70)
    print("Test 5: Statistics Queries")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Log various calls
    tracker.log_call("gpt-4", 1000, 500, thread_id="thread_1", user_id="user_1")
    tracker.log_call("gpt-4", 2000, 1000, thread_id="thread_1", user_id="user_1")
    tracker.log_call("claude-3-opus", 1500, 750, thread_id="thread_2", user_id="user_1")
    tracker.log_call("gpt-3.5-turbo", 500, 250, thread_id="thread_2", user_id="user_2")

    # Overall stats
    stats = tracker.get_stats()
    print(f"\nOverall stats:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total tokens: {stats['total_tokens']:,}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")
    print(f"  Avg cost/call: ${stats['average_cost_per_call']:.4f}")

    assert stats['total_calls'] == 4

    # By model
    print(f"\nBy model:")
    for model, data in stats['by_model'].items():
        print(f"  {model}: {data['calls']} calls, ${data['cost']:.4f}")

    assert "gpt-4" in stats['by_model']
    assert stats['by_model']['gpt-4']['calls'] == 2

    # By provider
    print(f"\nBy provider:")
    for provider, data in stats['by_provider'].items():
        print(f"  {provider}: {data['calls']} calls, ${data['cost']:.4f}")

    # Filter by thread
    thread_stats = tracker.get_stats(thread_id="thread_1")
    print(f"\nThread 1 stats:")
    print(f"  Calls: {thread_stats['total_calls']}")
    print(f"  Cost: ${thread_stats['total_cost']:.4f}")

    assert thread_stats['total_calls'] == 2

    # Filter by user
    user_stats = tracker.get_stats(user_id="user_1")
    print(f"\nUser 1 stats:")
    print(f"  Calls: {user_stats['total_calls']}")
    print(f"  Cost: ${user_stats['total_cost']:.4f}")

    assert user_stats['total_calls'] == 3

    print("\n[PASS] Statistics queries work correctly")
    return True


def test_top_expensive():
    """Test top expensive queries"""
    print("\n" + "=" * 70)
    print("Test 6: Top Expensive Queries")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Log calls with varying costs
    tracker.log_call("gpt-4", 10000, 5000, thread_id="expensive_thread")
    tracker.log_call("gpt-3.5-turbo", 1000, 500, thread_id="cheap_thread")
    tracker.log_call("claude-3-opus", 5000, 2500, thread_id="medium_thread")

    # Get top expensive threads
    top_threads = tracker.get_top_expensive(by="thread", limit=3)

    print(f"\nTop expensive threads:")
    for i, item in enumerate(top_threads, 1):
        print(f"  {i}. {item['id']}: ${item['cost']:.4f} ({item['calls']} calls)")

    assert len(top_threads) == 3
    assert top_threads[0]['id'] == "expensive_thread"  # Most expensive

    # Get top expensive models
    top_models = tracker.get_top_expensive(by="model", limit=3)

    print(f"\nTop expensive models:")
    for i, item in enumerate(top_models, 1):
        print(f"  {i}. {item['id']}: ${item['cost']:.4f} ({item['calls']} calls)")

    print("\n[PASS] Top expensive queries work correctly")
    return True


def test_scoped_budgets():
    """Test scoped budgets (thread, user, global)"""
    print("\n" + "=" * 70)
    print("Test 7: Scoped Budgets")
    print("=" * 70)

    tracker = CostTracker(db_path=":memory:")

    # Set thread-specific budget
    tracker.set_budget(limit=0.1, scope="thread", scope_id="thread_1")
    print("\nSet budget for thread_1: $0.10")

    # Log call within thread_1 budget
    tracker.log_call("gpt-3.5-turbo", 1000, 500, thread_id="thread_1")
    print("Call to thread_1: Success")

    # Check thread_1 budget
    budget = tracker.check_budget(thread_id="thread_1")
    print(f"Thread_1 budget: ${budget['current_spend']:.4f} / ${budget['budget_limit']:.2f}")

    # Log call to thread_2 (no budget set, should succeed)
    tracker.log_call("gpt-4", 10000, 5000, thread_id="thread_2")
    print("Call to thread_2 (no budget): Success")

    # Try to exceed thread_1 budget
    try:
        for _ in range(100):
            tracker.log_call("gpt-3.5-turbo", 1000, 500, thread_id="thread_1")
        print("[FAIL] Should have raised BudgetExceededError")
        return False
    except BudgetExceededError:
        print("Exceeded thread_1 budget: Correctly raised error")

    print("\n[PASS] Scoped budgets work correctly")
    return True


def main():
    """Run all tests"""

    print("\n")
    print("=" * 70)
    print("COST TRACKER TESTS")
    print("=" * 70)
    print()

    results = []

    # Test 1: Cost calculation
    try:
        success = test_cost_calculation()
        results.append(("Cost Calculation", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Cost Calculation", False))

    # Test 2: Logging
    try:
        success = test_logging()
        results.append(("Logging", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Logging", False))

    # Test 3: Budget check
    try:
        success = test_budget_check()
        results.append(("Budget Check", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Budget Check", False))

    # Test 4: Budget exceeded
    try:
        success = test_budget_exceeded()
        results.append(("Budget Exceeded", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Budget Exceeded", False))

    # Test 5: Statistics
    try:
        success = test_statistics()
        results.append(("Statistics", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Statistics", False))

    # Test 6: Top expensive
    try:
        success = test_top_expensive()
        results.append(("Top Expensive", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Top Expensive", False))

    # Test 7: Scoped budgets
    try:
        success = test_scoped_budgets()
        results.append(("Scoped Budgets", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        results.append(("Scoped Budgets", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name:<30} {status}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print("-" * 70)
    print(f"Total: {passed_count}/{total_count} passed")

    if passed_count == total_count:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("\nConclusion: Cost tracking is working correctly!")
    else:
        print(f"\n[WARN] {total_count - passed_count} test(s) failed")


if __name__ == "__main__":
    main()
