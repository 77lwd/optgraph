# -*- coding: utf-8 -*-
"""
Test Cost Tracking integration with LangGraph

Tests:
1. OptGraph.compile with cost tracking
2. Manual callback usage
3. Wrapper usage
4. Budget enforcement in real workflow
"""

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, AIMessage

# Mock LLM for testing
class MockLLM:
    """Mock LLM that simulates token usage"""

    def __init__(self, model: str = "gpt-4"):
        self.model_name = model
        self.callbacks = []

    def invoke(self, input_text):
        """Simulate LLM call"""
        # Simulate token usage based on input length
        input_tokens = len(input_text.split()) * 10
        output_tokens = 50

        # Create mock response
        response = MockLLMResult(
            model_name=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Trigger callbacks
        for callback in self.callbacks:
            if hasattr(callback, 'on_llm_end'):
                callback.on_llm_end(response)

        return f"Response to: {input_text}"


class MockLLMResult:
    """Mock LLM result with token usage"""

    def __init__(self, model_name, input_tokens, output_tokens):
        self.llm_output = {
            "model_name": model_name,
            "token_usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
            }
        }


def test_optgraph_compile_with_cost_tracking():
    """Test OptGraph.compile with cost tracking enabled"""
    print("=" * 70)
    print("Test 1: OptGraph.compile() with Cost Tracking")
    print("=" * 70)

    from optgraph import OptGraph, CostTracker

    # Create a simple graph
    def agent_node(state: MessagesState) -> MessagesState:
        return {"messages": [AIMessage(content="DONE")]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)

    # Compile with cost tracking
    app = OptGraph.compile(
        graph,
        enable_cost_tracking=True,
        cost_tracker_config={
            "db_path": ":memory:",
            "budget_limit": 10.0,
        }
    )

    # Verify cost tracker is attached
    assert hasattr(app, 'cost_tracker'), "app should have cost_tracker"
    assert isinstance(app.cost_tracker, CostTracker), "cost_tracker should be CostTracker instance"

    # Verify callback is attached
    assert hasattr(app, 'cost_tracking_callback'), "app should have cost_tracking_callback"

    print("\n[PASS] OptGraph.compile creates cost tracker")
    print(f"  Tracker: {app.cost_tracker}")
    print(f"  Callback: {app.cost_tracking_callback}")

    return True


def test_manual_callback():
    """Test manual callback usage"""
    print("\n" + "=" * 70)
    print("Test 2: Manual Callback Usage")
    print("=" * 70)

    from optgraph import CostTracker, CostTrackingCallback

    # Create tracker
    tracker = CostTracker(db_path=":memory:")
    tracker.set_budget(limit=1.0)

    # Create mock LLM
    llm = MockLLM(model="gpt-4")

    # Add callback
    callback = CostTrackingCallback(tracker, verbose=True)
    llm.callbacks.append(callback)

    # Call LLM
    print("\nCalling LLM with callback...")
    result = llm.invoke("Hello world")

    # Check stats
    stats = tracker.get_stats()
    print(f"\nStats after call:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")
    print(f"  Total tokens: {stats['total_tokens']}")

    assert stats['total_calls'] == 1, "Should have 1 call"
    assert stats['total_cost'] > 0, "Should have non-zero cost"

    print("\n[PASS] Manual callback works correctly")
    return True


def test_wrapper():
    """Test CostTrackedLLM wrapper"""
    print("\n" + "=" * 70)
    print("Test 3: CostTrackedLLM Wrapper")
    print("=" * 70)

    from optgraph import CostTracker, CostTrackedLLM

    # Create tracker
    tracker = CostTracker(db_path=":memory:")

    # Create mock LLM
    base_llm = MockLLM(model="claude-3-opus")

    # Wrap with cost tracking
    llm = CostTrackedLLM(base_llm, tracker, thread_id="test_thread")

    # Call LLM
    print("\nCalling wrapped LLM...")
    result = llm.invoke("Hello from wrapper")

    # Check stats
    stats = tracker.get_stats()
    print(f"\nStats after call:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")

    # Check thread-specific stats
    thread_stats = tracker.get_stats(thread_id="test_thread")
    print(f"\nThread-specific stats:")
    print(f"  Calls: {thread_stats['total_calls']}")
    print(f"  Cost: ${thread_stats['total_cost']:.4f}")

    assert stats['total_calls'] == 1
    assert thread_stats['total_calls'] == 1

    print("\n[PASS] Wrapper works correctly")
    return True


def test_enable_cost_tracking():
    """Test enable_cost_tracking convenience function"""
    print("\n" + "=" * 70)
    print("Test 4: enable_cost_tracking() Convenience Function")
    print("=" * 70)

    from optgraph import enable_cost_tracking

    # Create mock LLM
    base_llm = MockLLM(model="gpt-3.5-turbo")

    # Enable cost tracking (one-liner!)
    llm = enable_cost_tracking(base_llm, db_path=":memory:", budget_limit=5.0)

    # Make multiple calls
    print("\nMaking 3 calls...")
    for i in range(3):
        llm.invoke(f"Call {i+1}")

    # Check stats
    stats = llm.cost_tracker.get_stats()
    print(f"\nStats after 3 calls:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")

    # Check budget
    budget = llm.cost_tracker.check_budget()
    print(f"\nBudget status:")
    print(f"  Spent: ${budget['current_spend']:.4f}")
    print(f"  Limit: ${budget['budget_limit']:.2f}")
    print(f"  Usage: {budget['usage_percent']:.1f}%")

    assert stats['total_calls'] == 3
    assert budget['within_budget'] == True

    print("\n[PASS] Convenience function works correctly")
    return True


def test_budget_enforcement():
    """Test budget enforcement stops execution"""
    print("\n" + "=" * 70)
    print("Test 5: Budget Enforcement")
    print("=" * 70)

    from optgraph import CostTracker, CostTrackingCallback, BudgetExceededError

    # Create tracker with low budget
    tracker = CostTracker(db_path=":memory:")
    tracker.set_budget(limit=0.01)  # $0.01 budget

    # Create mock LLM with cheaper model
    llm = MockLLM(model="gpt-3.5-turbo")  # Cheaper than GPT-4
    callback = CostTrackingCallback(tracker)
    llm.callbacks.append(callback)

    # First call should succeed (short message, cheap model)
    print("\nFirst call (should succeed)...")
    llm.invoke("Hi")  # Very short
    print("  Success")

    # Check current spend
    budget = tracker.check_budget()
    print(f"  Current spend: ${budget['current_spend']:.6f}")
    print(f"  Budget limit: ${budget['budget_limit']:.2f}")

    # Multiple calls to accumulate cost and exceed budget
    print("\nMaking multiple calls to exceed budget...")
    call_count = 0
    try:
        for i in range(100):  # Keep calling until budget exceeded
            llm.invoke(f"This is call number {i} with some text to use tokens")
            call_count += 1
    except BudgetExceededError as e:
        print(f"  Budget exceeded after {call_count} additional calls")
        print(f"  Error: {e}")

    if call_count >= 100:
        print("  [FAIL] Should have exceeded budget before 100 calls")
        return False

    print("\n[PASS] Budget enforcement works correctly")
    return True


def test_real_workflow():
    """Test in a real LangGraph workflow"""
    print("\n" + "=" * 70)
    print("Test 6: Real LangGraph Workflow")
    print("=" * 70)

    from optgraph import OptGraph, CostTracker

    # Create tracker
    tracker = CostTracker(db_path=":memory:")
    tracker.set_budget(limit=10.0)

    # Define workflow with mock LLM
    def agent_node(state: MessagesState) -> MessagesState:
        llm = MockLLM(model="gpt-4")

        # Add cost tracking callback from tracker
        from optgraph import CostTrackingCallback
        callback = CostTrackingCallback(tracker, thread_id="workflow_123")
        llm.callbacks.append(callback)

        # Call LLM
        response = llm.invoke(str(state["messages"]))

        return {"messages": [AIMessage(content=response)]}

    def tools_node(state: MessagesState) -> MessagesState:
        return {"messages": [AIMessage(content="Tool result")]}

    def route(state: dict) -> Literal["tools", "__end__"]:
        return END

    # Build graph
    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", END)

    # Compile
    app = graph.compile()

    # Run workflow
    print("\nRunning workflow...")
    result = app.invoke({"messages": [HumanMessage(content="Test")]})

    # Check stats
    stats = tracker.get_stats()
    print(f"\nWorkflow stats:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Total cost: ${stats['total_cost']:.4f}")

    # Check thread stats
    thread_stats = tracker.get_stats(thread_id="workflow_123")
    print(f"\nThread 'workflow_123' stats:")
    print(f"  Calls: {thread_stats['total_calls']}")
    print(f"  Cost: ${thread_stats['total_cost']:.4f}")

    assert stats['total_calls'] >= 1
    assert thread_stats['total_calls'] >= 1

    print("\n[PASS] Real workflow integration works")
    return True


def main():
    """Run all integration tests"""

    print("\n")
    print("=" * 70)
    print("COST TRACKING INTEGRATION TESTS")
    print("=" * 70)
    print()

    results = []

    # Test 1: OptGraph.compile
    try:
        success = test_optgraph_compile_with_cost_tracking()
        results.append(("OptGraph.compile", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("OptGraph.compile", False))

    # Test 2: Manual callback
    try:
        success = test_manual_callback()
        results.append(("Manual Callback", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("Manual Callback", False))

    # Test 3: Wrapper
    try:
        success = test_wrapper()
        results.append(("Wrapper", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("Wrapper", False))

    # Test 4: Convenience function
    try:
        success = test_enable_cost_tracking()
        results.append(("Convenience Function", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("Convenience Function", False))

    # Test 5: Budget enforcement
    try:
        success = test_budget_enforcement()
        results.append(("Budget Enforcement", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("Budget Enforcement", False))

    # Test 6: Real workflow
    try:
        success = test_real_workflow()
        results.append(("Real Workflow", success))
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        results.append(("Real Workflow", False))

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
        print("\n[SUCCESS] ALL INTEGRATION TESTS PASSED!")
        print("\nConclusion: Cost tracking integration is working!")
    else:
        print(f"\n[WARN] {total_count - passed_count} test(s) failed")


if __name__ == "__main__":
    main()
