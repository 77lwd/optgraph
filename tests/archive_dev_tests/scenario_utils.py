"""
Shared utilities for scenario testing
"""

import json
import time
from pathlib import Path
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from optgraph.memory_state import (
    MemoryState,
    should_compress,
    compress_memory,
    get_context_with_memory
)
from optgraph.token_tracker import TokenTracker


def create_baseline_agent(llm_config):
    """Baseline: No compression"""
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


def create_memory_agent(llm_config, max_messages=20, keep_recent=10):
    """With memory compression"""
    main_llm = ChatOpenAI(**llm_config)
    tracker = TokenTracker()

    summarizer_config = llm_config.copy()
    summarizer_config["temperature"] = 0.3
    summarizer_llm = ChatOpenAI(**summarizer_config)

    def chat_node(state: MemoryState):
        messages = get_context_with_memory(state)
        response = main_llm.invoke(messages)
        tracker.record_usage(response)
        return {"messages": [response]}

    def compress_node(state: MemoryState):
        result = compress_memory(state, summarizer_llm, keep_recent)
        if result:
            tracker.record_request(input_tokens=200, output_tokens=50)
        return result

    def route_after_chat(state: MemoryState):
        return "compress" if should_compress(state, max_messages) else END

    builder = StateGraph(MemoryState)
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", route_after_chat, {"compress": "compress", END: END})
    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver()), tracker


def run_scenario_test(scenario_name, scenario_func, llm_config, expected_rounds):
    """
    Run one scenario test with baseline vs memory compression

    Returns:
        dict with test results
    """
    print("="*70)
    print(f"Scenario: {scenario_name}")
    print("="*70)
    print(f"Expected rounds: {expected_rounds}")
    print()

    results = {
        'scenario': scenario_name,
        'rounds': expected_rounds,
        'timestamp': time.time(),
    }

    # Baseline
    print("[1/2] Running BASELINE (no compression)...")
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"baseline-{int(time.time()*1000)}"}}

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

    # Memory compression
    print("[2/2] Running MEMORY COMPRESSION...")
    memory_agent, memory_tracker = create_memory_agent(llm_config)
    memory_config = {"configurable": {"thread_id": f"memory-{int(time.time()*1000)}"}}

    start_time = time.time()
    memory_result = scenario_func(memory_agent, memory_config)
    memory_time = time.time() - start_time

    memory_stats = memory_tracker.get_stats()
    print(f"  [OK] Completed in {memory_time:.1f}s")
    print(f"  [OK] Total tokens: {memory_stats['total_tokens']:,}")
    print()

    results['memory'] = {
        'tokens': memory_stats['total_tokens'],
        'requests': memory_stats['total_requests'],
        'time': memory_time,
    }

    # Calculate savings
    token_reduction = ((baseline_stats['total_tokens'] - memory_stats['total_tokens'])
                       / baseline_stats['total_tokens'] * 100) if baseline_stats['total_tokens'] > 0 else 0

    time_overhead = ((memory_time - baseline_time) / baseline_time * 100) if baseline_time > 0 else 0

    results['savings'] = {
        'token_reduction_percent': token_reduction,
        'time_overhead_percent': time_overhead,
    }

    # Quality check
    baseline_response = baseline_result['messages'][-1].content.lower()
    memory_response = memory_result['messages'][-1].content.lower()

    baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response)) / 2.0 * 100
    memory_quality = (('alice' in memory_response) + ('beijing' in memory_response)) / 2.0 * 100

    results['quality'] = {
        'baseline_percent': baseline_quality,
        'memory_percent': memory_quality,
    }

    # Print summary
    print("-"*70)
    print("RESULTS:")
    print("-"*70)
    print(f"Baseline:  {baseline_stats['total_tokens']:,} tokens, {baseline_time:.1f}s, Quality: {baseline_quality:.0f}%")
    print(f"Memory:    {memory_stats['total_tokens']:,} tokens, {memory_time:.1f}s, Quality: {memory_quality:.0f}%")
    print(f"Savings:   {token_reduction:+.1f}% tokens, {time_overhead:+.1f}% time")
    print("="*70)
    print()

    return results


def save_results(results, output_file):
    """Save results to JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[OK] Results saved to: {output_file}")
    print()


def load_existing_results(results_dir):
    """Load all existing result files"""
    results_path = Path(results_dir)
    if not results_path.exists():
        return []

    all_results = []
    for json_file in results_path.glob("scenario_*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            all_results.append(json.load(f))

    return all_results


def print_summary(all_results):
    """Print summary of all scenarios"""
    if not all_results:
        print("No results found.")
        return

    print("\n" + "="*70)
    print("SUMMARY: All Scenarios")
    print("="*70)
    print(f"{'Scenario':<35} {'Token Reduction':>15} {'Quality':>10}")
    print("-"*70)

    for r in all_results:
        savings = r['savings']['token_reduction_percent']
        quality = r['quality']['memory_percent']
        print(f"{r['scenario']:<35} {savings:>14.1f}% {quality:>9.0f}%")

    # Statistics
    reductions = [r['savings']['token_reduction_percent'] for r in all_results]
    avg_reduction = sum(reductions) / len(reductions)
    min_reduction = min(reductions)
    max_reduction = max(reductions)

    print("-"*70)
    print(f"{'Average':<35} {avg_reduction:>14.1f}%")
    print(f"{'Range':<35} {min_reduction:.1f}% - {max_reduction:.1f}%")
    print("="*70)
