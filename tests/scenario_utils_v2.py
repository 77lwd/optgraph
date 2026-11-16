"""
Scenario testing utilities for Memory v2.0

Allows running the same scenario tests but with the new memory system
"""

import json
import time
from pathlib import Path
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from optgraph.memory_v2 import (
    MemoryStateV2,
    MemoryCompressor,
    should_compress_v2,
    compress_memory_v2,
    get_context_baseline,
    get_context_with_recall,
    needs_recall
)
from optgraph.token_tracker import TokenTracker


def create_baseline_agent(llm_config):
    """Baseline: No compression, no memory"""
    main_llm = ChatOpenAI(**llm_config)
    tracker = TokenTracker()

    def chat_node(state: MessagesState):
        response = main_llm.invoke(state["messages"])
        tracker.record_usage(response)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)

    return builder.compile(checkpointer=MemorySaver()), tracker


def create_memory_v2_agent(llm_config, max_messages=20, keep_recent=10):
    """
    Memory v2.0 agent for scenario testing

    Key features:
    - Zero overhead by default (no memory passed)
    - Structured storage
    - On-demand retrieval
    """
    main_llm = ChatOpenAI(**llm_config)
    tracker = TokenTracker()

    compressor_config = llm_config.copy()
    compressor_config["temperature"] = 0.3
    compressor_llm = ChatOpenAI(**compressor_config)

    compressor = MemoryCompressor(compressor_llm)

    def chat_node(state: MemoryStateV2):
        """Chat without memory (baseline path)"""
        messages = get_context_baseline(state)
        response = main_llm.invoke(messages)
        tracker.record_usage(response)
        return {"messages": [response]}

    def recall_node(state: MemoryStateV2):
        """Chat with memory retrieval"""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        query = str(last_message.content)

        messages_with_memory = get_context_with_recall(state, query, top_k=3)
        response = main_llm.invoke(messages_with_memory)
        tracker.record_usage(response)
        return {"messages": [response]}

    def compress_node(state: MemoryStateV2):
        """Compress old messages to structured storage"""
        result = compress_memory_v2(state, compressor, keep_recent)

        # Track compression cost (LLM call for extraction)
        if result and result.get("structured_memory"):
            tracker.record_request(input_tokens=200, output_tokens=50)

        return result

    def route_entry(state: MemoryStateV2):
        """Route to recall or chat"""
        messages = state.get("messages", [])
        if not messages:
            return "chat"

        last_message = messages[-1]
        user_message = str(last_message.content)

        if needs_recall(user_message):
            return "recall"
        return "chat"

    def route_after_chat(state: MemoryStateV2):
        """Route to compression or end"""
        return "compress" if should_compress_v2(state, max_messages) else END

    # Build graph
    builder = StateGraph(MemoryStateV2)
    builder.add_node("chat", chat_node)
    builder.add_node("recall", recall_node)
    builder.add_node("compress", compress_node)

    # Entry routing
    builder.add_conditional_edges(
        START,
        route_entry,
        {
            "chat": "chat",
            "recall": "recall"
        }
    )

    # After chat/recall: check compression
    builder.add_conditional_edges(
        "chat",
        route_after_chat,
        {
            "compress": "compress",
            END: END
        }
    )

    builder.add_conditional_edges(
        "recall",
        route_after_chat,
        {
            "compress": "compress",
            END: END
        }
    )

    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver()), tracker


def run_scenario_test_v2(scenario_name, scenario_func, llm_config, expected_rounds):
    """
    Run scenario test: baseline vs memory v2.0

    Args:
        scenario_name: Name of the scenario
        scenario_func: Function that runs the scenario (takes agent, config)
        llm_config: LLM configuration
        expected_rounds: Expected number of rounds

    Returns:
        dict with test results
    """
    print("="*70)
    print(f"Scenario: {scenario_name} (Memory v2.0)")
    print("="*70)
    print(f"Expected rounds: {expected_rounds}")
    print()

    results = {
        'scenario': scenario_name,
        'version': 'memory_v2.0',
        'rounds': expected_rounds,
        'timestamp': time.time(),
    }

    # Baseline
    print("[1/2] Running BASELINE (no memory)...")
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"baseline-v2-{int(time.time()*1000)}"}}

    start_time = time.time()
    baseline_result = scenario_func(baseline_agent, baseline_config)
    baseline_time = time.time() - start_time

    baseline_stats = baseline_tracker.get_stats()
    print(f"  [OK] Completed in {baseline_time:.1f}s")
    print(f"  [OK] Total tokens: {baseline_stats['total_tokens']:,}")
    print()

    results['baseline'] = {
        'tokens': baseline_stats['total_tokens'],
        'requests': baseline_stats['total_requests'],
        'time': baseline_time,
    }

    # Memory v2.0
    print("[2/2] Running MEMORY v2.0...")
    memory_agent, memory_tracker = create_memory_v2_agent(llm_config)
    memory_config = {"configurable": {"thread_id": f"memory-v2-{int(time.time()*1000)}"}}

    start_time = time.time()
    memory_result = scenario_func(memory_agent, memory_config)
    memory_time = time.time() - start_time

    memory_stats = memory_tracker.get_stats()
    print(f"  [OK] Completed in {memory_time:.1f}s")
    print(f"  [OK] Total tokens: {memory_stats['total_tokens']:,}")
    print()

    results['memory_v2'] = {
        'tokens': memory_stats['total_tokens'],
        'requests': memory_stats['total_requests'],
        'time': memory_time,
    }

    # Calculate metrics
    token_diff = memory_stats['total_tokens'] - baseline_stats['total_tokens']
    token_change_percent = (token_diff / baseline_stats['total_tokens'] * 100) if baseline_stats['total_tokens'] > 0 else 0

    time_overhead = ((memory_time - baseline_time) / baseline_time * 100) if baseline_time > 0 else 0

    results['comparison'] = {
        'token_difference': token_diff,
        'token_change_percent': token_change_percent,
        'time_overhead_percent': time_overhead,
    }

    # Quality check
    baseline_response = baseline_result['messages'][-1].content.lower()
    memory_response = memory_result['messages'][-1].content.lower()

    baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response)) / 2.0 * 100
    memory_quality = (('alice' in memory_response) + ('beijing' in memory_response)) / 2.0 * 100

    results['quality'] = {
        'baseline_percent': baseline_quality,
        'memory_v2_percent': memory_quality,
    }

    # Print summary
    print("-"*70)
    print("RESULTS:")
    print("-"*70)
    print(f"Baseline:    {baseline_stats['total_tokens']:,} tokens, {baseline_time:.1f}s, Quality: {baseline_quality:.0f}%")
    print(f"Memory v2:   {memory_stats['total_tokens']:,} tokens, {memory_time:.1f}s, Quality: {memory_quality:.0f}%")
    print(f"Difference:  {token_diff:+,} tokens ({token_change_percent:+.1f}%), {time_overhead:+.1f}% time")
    print()

    # Interpretation
    if abs(token_change_percent) < 5:
        print(f"  Result: ~ZERO OVERHEAD ({token_change_percent:+.1f}%) - as expected for v2!")
    elif token_change_percent < -10:
        print(f"  Result: SAVINGS ({token_change_percent:.1f}%) - better than expected!")
    elif token_change_percent > 10:
        print(f"  Result: OVERHEAD ({token_change_percent:+.1f}%) - needs investigation")

    print("="*70)
    print()

    return results


def save_results_v2(results, output_file):
    """Save v2 results to JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[OK] Results saved to: {output_file}")
    print()


def print_comparison_v1_v2(v1_results_file, v2_results_file):
    """
    Print comparison between v1 and v2 results

    Args:
        v1_results_file: Path to v1 results JSON
        v2_results_file: Path to v2 results JSON
    """
    with open(v1_results_file, 'r') as f:
        v1 = json.load(f)

    with open(v2_results_file, 'r') as f:
        v2 = json.load(f)

    print("\n" + "="*70)
    print(f"Comparison: {v1['scenario']}")
    print("="*70)

    print("\n{:<20} {:>15} {:>15} {:>15}".format(
        "Metric", "Baseline", "Memory v1", "Memory v2"
    ))
    print("-"*70)

    baseline_tokens = v1['baseline']['tokens']
    v1_tokens = v1['memory']['tokens']
    v2_tokens = v2['memory_v2']['tokens']

    print("{:<20} {:>15,} {:>15,} {:>15,}".format(
        "Total tokens",
        baseline_tokens,
        v1_tokens,
        v2_tokens
    ))

    v1_change = ((v1_tokens - baseline_tokens) / baseline_tokens * 100)
    v2_change = ((v2_tokens - baseline_tokens) / baseline_tokens * 100)

    print("{:<20} {:>15} {:>14.1f}% {:>14.1f}%".format(
        "vs Baseline",
        "0%",
        v1_change,
        v2_change
    ))

    print("\n" + "="*70)
    print("Summary:")
    print(f"  v1: {v1_change:+.1f}% vs baseline")
    print(f"  v2: {v2_change:+.1f}% vs baseline")
    print(f"  Improvement: v2 is {v1_change - v2_change:.1f}% better than v1")
    print("="*70)
