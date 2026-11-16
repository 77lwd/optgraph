"""
Real-world compression comparison test

Compares baseline (no compression) vs compression using the same user input sequence.
Measures actual prompt_tokens from API responses to show real token savings.

Strategy:
1. Run baseline conversation (threshold=999999, never compress)
2. Run compressed conversation (threshold=4000, keep_recent=10) with SAME user inputs
3. Compare cumulative prompt_tokens from API responses
"""

import os
import json
import time
from datetime import datetime
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.token_tracker import TokenTracker


# Configuration
API_KEY = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"
MODEL = "deepseek-v4.1-flash"
BASE_URL = "https://beeapi.dev/v1"


def create_chat_agent(checkpointer, tracker):
    """Create a chat agent with compression and token tracking"""

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.7,
    )

    def chat_node(state):
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


def generate_user_inputs(rounds):
    """Generate fixed user input sequence

    Returns list of user messages for consistent testing
    """
    topics = [
        "Python", "Java", "JavaScript", "C++", "Go", "Rust", "Swift", "Kotlin",
        "Ruby", "PHP", "TypeScript", "Scala", "Haskell", "Erlang", "Clojure",
        "R", "MATLAB", "Perl", "Lua", "Dart"
    ]

    inputs = []
    for i in range(rounds):
        topic = topics[i % len(topics)]
        inputs.append("Tell me about {} in 2-3 sentences.".format(topic))

    return inputs


def run_conversation(threshold, keep_recent, user_inputs, label):
    """Run a conversation with given parameters

    Args:
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep
        user_inputs: List of user input strings
        label: Label for this test run

    Returns:
        Dict with test results
    """
    print("\n" + "="*70)
    print("[{}] threshold={}, keep_recent={}".format(label, threshold, keep_recent))
    print("="*70)

    # Create tracker and checkpointer
    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=threshold,
        keep_recent=keep_recent
    )

    # Create agent
    agent = create_chat_agent(checkpointer, tracker)

    # Use unique thread_id
    thread_id = "{}-{}".format(label.lower().replace(" ", "-"), int(time.time()*1000))
    config = {"configurable": {"thread_id": thread_id}}

    start_time = time.time()

    # Track per-round prompt tokens
    round_stats = []

    # Run conversation
    for i, user_input in enumerate(user_inputs, 1):
        round_start = time.time()

        # Get tokens before this call
        before_stats = tracker.get_stats()
        before_prompt_tokens = before_stats['total_prompt_tokens']

        # Make the call
        agent.invoke(
            {"messages": [("user", user_input)]},
            config
        )

        # Get tokens after this call
        after_stats = tracker.get_stats()
        after_prompt_tokens = after_stats['total_prompt_tokens']

        # Calculate prompt tokens for this round
        round_prompt_tokens = after_prompt_tokens - before_prompt_tokens

        round_elapsed = time.time() - round_start

        round_stats.append({
            "round": i,
            "prompt_tokens": round_prompt_tokens,
            "elapsed": round_elapsed
        })

        # Print progress every 10 rounds
        if i % 10 == 0:
            comp_stats = checkpointer.get_compression_stats()
            print("[Round {}/{}] prompt_tokens={}, compressions={}".format(
                i, len(user_inputs), round_prompt_tokens, comp_stats['total_compressions']))

    elapsed = time.time() - start_time

    # Get final stats
    comp_stats = checkpointer.get_compression_stats()
    token_stats = tracker.get_stats()

    print("\n[{}] RESULTS:".format(label))
    print("  Total rounds: {}".format(len(user_inputs)))
    print("  Total prompt tokens: {}".format(token_stats['total_prompt_tokens']))
    print("  Total completion tokens: {}".format(token_stats['total_completion_tokens']))
    print("  Total tokens: {}".format(token_stats['total_tokens']))
    print("  Compressions: {}".format(comp_stats['total_compressions']))
    print("  Elapsed time: {:.1f}s".format(elapsed))

    return {
        "label": label,
        "threshold": threshold,
        "keep_recent": keep_recent,
        "rounds": len(user_inputs),
        "total_prompt_tokens": token_stats['total_prompt_tokens'],
        "total_completion_tokens": token_stats['total_completion_tokens'],
        "total_tokens": token_stats['total_tokens'],
        "compressions": comp_stats['total_compressions'],
        "elapsed_time": elapsed,
        "round_stats": round_stats
    }


def main():
    """Run real compression comparison test"""
    print("\n" + "="*70)
    print("Real-world Compression Comparison Test")
    print("="*70)
    print("Start time: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Generate fixed user input sequence
    rounds = 50
    user_inputs = generate_user_inputs(rounds)

    print("\nTest configuration:")
    print("  Rounds: {}".format(rounds))
    print("  User inputs: {} unique messages".format(len(user_inputs)))

    # Test 1: Baseline (no compression)
    print("\n" + ">"*70)
    print("TEST 1: BASELINE (No Compression)")
    print(">"*70)
    baseline_result = run_conversation(
        threshold=999999,  # Never compress
        keep_recent=10,
        user_inputs=user_inputs,
        label="Baseline"
    )

    # Wait a bit between tests
    print("\nWaiting 3 seconds before next test...")
    time.sleep(3)

    # Test 2: With compression (threshold=3000)
    print("\n" + ">"*70)
    print("TEST 2: WITH COMPRESSION (threshold=3000)")
    print(">"*70)
    compressed_3000_result = run_conversation(
        threshold=3000,
        keep_recent=10,
        user_inputs=user_inputs,
        label="Compressed-3000"
    )

    # Wait a bit between tests
    print("\nWaiting 3 seconds before next test...")
    time.sleep(3)

    # Test 3: With compression (threshold=2000)
    print("\n" + ">"*70)
    print("TEST 3: WITH COMPRESSION (threshold=2000)")
    print(">"*70)
    compressed_2000_result = run_conversation(
        threshold=2000,
        keep_recent=10,
        user_inputs=user_inputs,
        label="Compressed-2000"
    )

    # Calculate comparison for both thresholds
    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)

    baseline_prompt = baseline_result['total_prompt_tokens']
    baseline_total = baseline_result['total_tokens']

    # Comparison with threshold=3000
    print("\n--- Threshold = 3000 ---")
    compressed_3000_prompt = compressed_3000_result['total_prompt_tokens']
    compressed_3000_total = compressed_3000_result['total_tokens']

    prompt_reduction_3000 = baseline_prompt - compressed_3000_prompt
    prompt_reduction_pct_3000 = (prompt_reduction_3000 / float(baseline_prompt)) * 100 if baseline_prompt > 0 else 0

    total_reduction_3000 = baseline_total - compressed_3000_total
    total_reduction_pct_3000 = (total_reduction_3000 / float(baseline_total)) * 100 if baseline_total > 0 else 0

    print("Prompt Tokens:")
    print("  Baseline:   {:,} tokens".format(baseline_prompt))
    print("  Compressed: {:,} tokens".format(compressed_3000_prompt))
    print("  Reduction:  {:,} tokens ({:.1f}%)".format(prompt_reduction_3000, prompt_reduction_pct_3000))
    print("Compressions triggered: {}".format(compressed_3000_result['compressions']))

    # Comparison with threshold=2000
    print("\n--- Threshold = 2000 ---")
    compressed_2000_prompt = compressed_2000_result['total_prompt_tokens']
    compressed_2000_total = compressed_2000_result['total_tokens']

    prompt_reduction_2000 = baseline_prompt - compressed_2000_prompt
    prompt_reduction_pct_2000 = (prompt_reduction_2000 / float(baseline_prompt)) * 100 if baseline_prompt > 0 else 0

    total_reduction_2000 = baseline_total - compressed_2000_total
    total_reduction_pct_2000 = (total_reduction_2000 / float(baseline_total)) * 100 if baseline_total > 0 else 0

    print("Prompt Tokens:")
    print("  Baseline:   {:,} tokens".format(baseline_prompt))
    print("  Compressed: {:,} tokens".format(compressed_2000_prompt))
    print("  Reduction:  {:,} tokens ({:.1f}%)".format(prompt_reduction_2000, prompt_reduction_pct_2000))
    print("Compressions triggered: {}".format(compressed_2000_result['compressions']))

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("Baseline (no compression): {:,} prompt tokens".format(baseline_prompt))
    print("With threshold=3000: {:.1f}% reduction, {} compressions".format(
        prompt_reduction_pct_3000, compressed_3000_result['compressions']))
    print("With threshold=2000: {:.1f}% reduction, {} compressions".format(
        prompt_reduction_pct_2000, compressed_2000_result['compressions']))

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "rounds": rounds,
        "baseline": baseline_result,
        "compressed_3000": compressed_3000_result,
        "compressed_2000": compressed_2000_result,
        "comparison": {
            "threshold_3000": {
                "prompt_tokens_saved": prompt_reduction_3000,
                "prompt_tokens_reduction_pct": prompt_reduction_pct_3000,
                "total_tokens_saved": total_reduction_3000,
                "total_tokens_reduction_pct": total_reduction_pct_3000,
            },
            "threshold_2000": {
                "prompt_tokens_saved": prompt_reduction_2000,
                "prompt_tokens_reduction_pct": prompt_reduction_pct_2000,
                "total_tokens_saved": total_reduction_2000,
                "total_tokens_reduction_pct": total_reduction_pct_2000,
            }
        }
    }

    output_file = "benchmarks/real_compression_results.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to: {}".format(output_file))
    print("="*70)


if __name__ == "__main__":
    main()
