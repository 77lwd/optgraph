"""
Phase 3: Parameter Search for Optimal Compression Configuration

Finds the optimal threshold and keep_recent parameters using:
1. Binary search for keep_recent (quality constraint: >90%)
2. Grid search for threshold (efficiency optimization: maximize token reduction)
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Tuple
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.token_tracker import TokenTracker


# Configuration
API_KEY = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"
MODEL = "deepseek-v4.1-flash"
BASE_URL = "https://beeapi.dev/v1"


def create_chat_agent(checkpointer, tracker: TokenTracker):
    """Create a chat agent with compression and token tracking"""

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.7,
    )

    def chat_node(state: MessagesState):
        """Chat node that calls LLM and tracks tokens"""
        response = llm.invoke(state["messages"])

        # Record token usage
        tracker.record_usage(response)

        return {"messages": [response]}

    # Build graph
    graph = StateGraph(MessagesState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.set_finish_point("chat")

    return graph.compile(checkpointer=checkpointer)


def test_memory_retention(threshold: int, keep_recent: int) -> Dict[str, Any]:
    """Test memory retention with given parameters

    Simulates a 16-round conversation where:
    - Round 1: User provides name and city
    - Round 16: Agent should remember both

    Args:
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep

    Returns:
        Dict with quality_score (0-1) and compression stats
    """
    print(f"\n[Memory Test] threshold={threshold}, keep_recent={keep_recent}")

    # Create tracker and checkpointer
    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=threshold,
        keep_recent=keep_recent
    )

    # Create agent
    agent = create_chat_agent(checkpointer, tracker)

    # Use timestamp to ensure unique thread_id
    thread_id = f"mem-test-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: Provide information
    agent.invoke(
        {"messages": [("user", "Hi, my name is Alice and I live in Beijing.")]},
        config
    )

    # Rounds 2-15: Filler conversation
    topics = ["weather", "food", "music", "movies", "sports",
              "books", "travel", "technology", "art", "history",
              "science", "games", "pets", "nature"]

    for i, topic in enumerate(topics, 2):
        agent.invoke(
            {"messages": [("user", f"Tell me something interesting about {topic} in one sentence.")]},
            config
        )

    # Round 16: Test recall
    result = agent.invoke(
        {"messages": [("user", "What is my name and where do I live?")]},
        config
    )

    # Check if agent remembers
    response = result['messages'][-1].content.lower()
    remembers_name = 'alice' in response
    remembers_city = 'beijing' in response

    # Quality score
    quality_score = (int(remembers_name) + int(remembers_city)) / 2.0

    # Get stats
    comp_stats = checkpointer.get_compression_stats()
    token_stats = tracker.get_stats()

    print(f"  Remembers name: {remembers_name}")
    print(f"  Remembers city: {remembers_city}")
    print(f"  Quality score: {quality_score:.1%}")
    print(f"  Compressions: {comp_stats['total_compressions']}")
    print(f"  Total tokens: {token_stats['total_tokens']}")

    return {
        "quality_score": quality_score,
        "remembers_name": remembers_name,
        "remembers_city": remembers_city,
        "compressions": comp_stats['total_compressions'],
        "total_tokens": token_stats['total_tokens'],
    }


def find_min_keep_recent(
    min_val: int = 5,
    max_val: int = 25,
    quality_threshold: float = 0.9
) -> Tuple[int, Dict[str, Any]]:
    """Binary search for minimum keep_recent that maintains quality

    Args:
        min_val: Lower bound for search
        max_val: Upper bound for search
        quality_threshold: Minimum acceptable quality (default 0.9 = 90%)

    Returns:
        Tuple of (optimal_keep_recent, test_results_dict)
    """
    print("\n" + "="*60)
    print("Phase 1: Finding Minimum keep_recent")
    print("="*60)
    print(f"Target quality: >={quality_threshold:.0%}")
    print(f"Search range: [{min_val}, {max_val}]")

    result = max_val  # Worst case fallback
    test_results = []

    while min_val <= max_val:
        mid = (min_val + max_val) // 2

        print(f"\n--- Iteration: Testing keep_recent={mid} ---")

        # Run memory retention test with high threshold (don't trigger compression too often)
        test_result = test_memory_retention(
            threshold=10000,  # High threshold to avoid interference
            keep_recent=mid
        )

        test_results.append({
            "keep_recent": mid,
            **test_result
        })

        quality = test_result['quality_score']

        if quality >= quality_threshold:
            # Quality is good, try smaller value
            print(f"  [OK] Quality {quality:.0%} >= {quality_threshold:.0%}, trying smaller...")
            result = mid
            max_val = mid - 1
        else:
            # Quality insufficient, need larger value
            print(f"  [FAIL] Quality {quality:.0%} < {quality_threshold:.0%}, need larger...")
            min_val = mid + 1

    print(f"\n{'='*60}")
    print(f"Result: Minimum keep_recent = {result}")
    print(f"{'='*60}")

    return result, {"iterations": test_results, "optimal_keep_recent": result}


def test_long_conversation(threshold: int, keep_recent: int, rounds: int = 30) -> Dict[str, Any]:
    """Test compression efficiency over a long conversation

    Args:
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep
        rounds: Number of conversation rounds

    Returns:
        Dict with token stats and compression metrics
    """
    print(f"\n[Long Conversation Test] threshold={threshold}, keep_recent={keep_recent}, rounds={rounds}")

    # Create tracker and checkpointer
    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=threshold,
        keep_recent=keep_recent
    )

    # Create agent
    agent = create_chat_agent(checkpointer, tracker)

    # Use timestamp to ensure unique thread_id
    thread_id = f"long-test-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    start_time = time.time()

    # Run conversation
    topics = ["Python", "Java", "JavaScript", "C++", "Go", "Rust", "Swift", "Kotlin",
              "Ruby", "PHP", "TypeScript", "Scala", "Haskell", "Erlang", "Clojure"]

    for i in range(rounds):
        topic = topics[i % len(topics)]
        agent.invoke(
            {"messages": [("user", f"Tell me about {topic} in 2-3 sentences.")]},
            config
        )

    elapsed = time.time() - start_time

    # Get stats
    comp_stats = checkpointer.get_compression_stats()
    token_stats = tracker.get_stats()

    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Compressions: {comp_stats['total_compressions']}")
    print(f"  Total tokens: {token_stats['total_tokens']}")
    print(f"  Avg tokens/call: {token_stats['total_tokens'] / token_stats['api_calls']:.0f}")

    return {
        "threshold": threshold,
        "keep_recent": keep_recent,
        "rounds": rounds,
        "elapsed_time": elapsed,
        "compressions": comp_stats['total_compressions'],
        "total_tokens": token_stats['total_tokens'],
        "prompt_tokens": token_stats['total_prompt_tokens'],
        "completion_tokens": token_stats['total_completion_tokens'],
        "api_calls": token_stats['api_calls'],
    }


def grid_search_threshold(
    keep_recent: int,
    threshold_values: list = [2000, 4000, 6000, 8000, 10000]
) -> Tuple[int, Dict[str, Any]]:
    """Grid search for optimal threshold given fixed keep_recent

    Args:
        keep_recent: Fixed keep_recent value from phase 1
        threshold_values: List of threshold values to test

    Returns:
        Tuple of (optimal_threshold, test_results_dict)
    """
    print("\n" + "="*60)
    print("Phase 2: Grid Search for Optimal Threshold")
    print("="*60)
    print(f"Fixed keep_recent: {keep_recent}")
    print(f"Testing thresholds: {threshold_values}")

    # First, run baseline (no compression)
    print("\n--- Baseline (No Compression) ---")
    baseline_tracker = TokenTracker()
    baseline_checkpointer = AdaptiveCheckpointSaver(
        threshold=999999,  # Never compress
        keep_recent=keep_recent
    )
    baseline_agent = create_chat_agent(baseline_checkpointer, baseline_tracker)

    baseline_thread_id = f"baseline-{int(time.time()*1000)}"
    baseline_config = {"configurable": {"thread_id": baseline_thread_id}}

    baseline_start = time.time()
    for i in range(30):
        topics = ["Python", "Java", "JavaScript", "C++", "Go"]
        topic = topics[i % len(topics)]
        baseline_agent.invoke(
            {"messages": [("user", f"Tell me about {topic} in 2-3 sentences.")]},
            baseline_config
        )
    baseline_elapsed = time.time() - baseline_start
    baseline_stats = baseline_tracker.get_stats()
    baseline_tokens = baseline_stats['total_tokens']

    print(f"  Baseline tokens: {baseline_tokens}")
    print(f"  Baseline time: {baseline_elapsed:.1f}s")

    # Test each threshold
    test_results = []
    best_threshold = threshold_values[0]
    best_reduction = 0

    for threshold in threshold_values:
        print(f"\n--- Testing threshold={threshold} ---")

        result = test_long_conversation(threshold, keep_recent, rounds=30)

        # Calculate token reduction
        compressed_tokens = result['total_tokens']
        reduction_pct = ((baseline_tokens - compressed_tokens) / baseline_tokens) * 100 if baseline_tokens > 0 else 0

        result['baseline_tokens'] = baseline_tokens
        result['token_reduction_pct'] = reduction_pct
        result['baseline_time'] = baseline_elapsed

        test_results.append(result)

        print(f"  Token reduction: {reduction_pct:.1f}%")

        if reduction_pct > best_reduction:
            best_reduction = reduction_pct
            best_threshold = threshold

    print(f"\n{'='*60}")
    print(f"Result: Optimal threshold = {best_threshold}")
    print(f"Best token reduction: {best_reduction:.1f}%")
    print(f"{'='*60}")

    return best_threshold, {
        "baseline": {
            "tokens": baseline_tokens,
            "time": baseline_elapsed
        },
        "tests": test_results,
        "optimal_threshold": best_threshold,
        "best_reduction_pct": best_reduction
    }


def main():
    """Run complete parameter search"""
    print("\n" + "="*70)
    print("OptGraph Phase 3: Parameter Optimization")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start_time = time.time()

    # Phase 1: Find optimal keep_recent
    optimal_keep_recent, phase1_results = find_min_keep_recent(
        min_val=5,
        max_val=25,
        quality_threshold=0.9
    )

    # Phase 2: Find optimal threshold
    optimal_threshold, phase2_results = grid_search_threshold(
        keep_recent=optimal_keep_recent,
        threshold_values=[2000, 4000, 6000, 8000, 10000]
    )

    elapsed = time.time() - start_time

    # Final results
    results = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_time": elapsed,
        "phase1_keep_recent": phase1_results,
        "phase2_threshold": phase2_results,
        "final_config": {
            "threshold": optimal_threshold,
            "keep_recent": optimal_keep_recent,
        }
    }

    # Save results
    output_file = "benchmarks/parameter_search_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Optimal keep_recent: {optimal_keep_recent}")
    print(f"Optimal threshold: {optimal_threshold}")
    print(f"Token reduction: {phase2_results['best_reduction_pct']:.1f}%")
    print(f"Total search time: {elapsed:.1f}s")
    print(f"\nResults saved to: {output_file}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
