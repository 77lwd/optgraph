# -*- coding: utf-8 -*-
"""
Week 2 Phase 2: Context Compression Benchmark
Validate compression quality with real LLM agent
"""

import os
import time
import json
from typing import Dict, List, Any
from datetime import datetime

from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from optgraph.checkpointer import AdaptiveCheckpointSaver


# ============================================================================
# Agent Creation
# ============================================================================

def create_agent(use_compression: bool = False, **compression_kwargs):
    """Create a conversational agent with optional compression

    Args:
        use_compression: Whether to use AdaptiveCheckpointSaver
        **compression_kwargs: Arguments for AdaptiveCheckpointSaver

    Returns:
        Compiled agent graph
    """
    # Choose checkpointer
    if use_compression:
        checkpointer = AdaptiveCheckpointSaver(**compression_kwargs)
    else:
        checkpointer = MemorySaver()

    # Define agent node
    def agent_node(state: MessagesState):
        """Agent that responds to user messages"""
        messages = state["messages"]

        # 使用 beeapi.dev 中转站
        llm = ChatOpenAI(
            model="deepseek-v4.1-flash",
            temperature=0.7,
            base_url="https://beeapi.dev/v1"
        )

        response = llm.invoke(messages)
        return {"messages": [response]}

    # Build graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)

    return workflow.compile(checkpointer=checkpointer), checkpointer


# ============================================================================
# Test Scenarios
# ============================================================================

def test_memory_retention(use_compression: bool) -> Dict[str, Any]:
    """Test: Can agent remember information after compression?

    Scenario:
    1. User provides personal info (name, city)
    2. Have 15 rounds of conversation (trigger compression)
    3. Ask agent to recall the info

    Returns:
        Test results with metrics
    """
    print(f"\n{'='*60}")
    print(f"Test: Memory Retention ({'Compressed' if use_compression else 'Baseline'})")
    print(f"{'='*60}")

    # Create agent
    if use_compression:
        agent, checkpointer = create_agent(
            use_compression=True,
            threshold=500,  # Low threshold to trigger compression quickly
            keep_recent=5
        )
    else:
        agent, checkpointer = create_agent(use_compression=False)

    config = {"configurable": {"thread_id": "memory-test"}}

    # Track metrics
    total_tokens = 0
    start_time = time.time()

    # Round 1: User provides info
    print("\n[Round 1] User provides personal info...")
    response = agent.invoke({
        "messages": [
            SystemMessage(content="You are a helpful assistant. Remember user information."),
            HumanMessage(content="Hi! My name is Alice and I live in Beijing.")
        ]
    }, config)
    print(f"Agent: {response['messages'][-1].content[:100]}...")

    # Rounds 2-15: Filler conversation to trigger compression
    filler_questions = [
        "What's the weather like today?",
        "Tell me about Python programming.",
        "What is machine learning?",
        "How do I learn to code?",
        "What are the best practices for REST APIs?",
        "Explain what a database is.",
        "What is cloud computing?",
        "Tell me about Docker.",
        "What is Kubernetes?",
        "Explain microservices architecture.",
        "What is CI/CD?",
        "Tell me about version control.",
        "What is agile development?",
        "Explain test-driven development."
    ]

    for i, question in enumerate(filler_questions, start=2):
        print(f"\n[Round {i}] Filler conversation...")
        response = agent.invoke({
            "messages": [HumanMessage(content=question)]
        }, config)
        print(f"Q: {question[:50]}...")
        print(f"A: {response['messages'][-1].content[:80]}...")

    # Round 16: Ask agent to recall info
    print(f"\n[Round 16] Testing memory recall...")
    response = agent.invoke({
        "messages": [HumanMessage(content="What's my name and where do I live?")]
    }, config)
    final_response = response['messages'][-1].content
    print(f"Agent: {final_response}")

    # Check if agent remembers
    remembers_name = "alice" in final_response.lower()
    remembers_city = "beijing" in final_response.lower()

    # Get compression stats
    if use_compression:
        stats = checkpointer.get_compression_stats()
        total_compressions = stats['total_compressions']
        token_reduction = stats['avg_token_reduction_percent']
    else:
        total_compressions = 0
        token_reduction = 0.0

    elapsed_time = time.time() - start_time

    # Results
    results = {
        "test": "memory_retention",
        "use_compression": use_compression,
        "rounds": 16,
        "remembers_name": remembers_name,
        "remembers_city": remembers_city,
        "quality_score": (int(remembers_name) + int(remembers_city)) / 2,
        "total_compressions": total_compressions,
        "token_reduction_percent": token_reduction,
        "elapsed_time": round(elapsed_time, 2)
    }

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Remembers name: {'YES' if remembers_name else 'NO'}")
    print(f"  Remembers city: {'YES' if remembers_city else 'NO'}")
    print(f"  Quality score: {results['quality_score']:.1%}")
    print(f"  Compressions: {total_compressions}")
    print(f"  Token reduction: {token_reduction:.1f}%")
    print(f"  Time: {elapsed_time:.2f}s")
    print(f"{'='*60}")

    return results


def test_long_conversation(use_compression: bool, num_rounds: int = 30) -> Dict[str, Any]:
    """Test: Long conversation performance

    Args:
        use_compression: Whether to use compression
        num_rounds: Number of conversation rounds

    Returns:
        Test results with metrics
    """
    print(f"\n{'='*60}")
    print(f"Test: Long Conversation - {num_rounds} rounds ({'Compressed' if use_compression else 'Baseline'})")
    print(f"{'='*60}")

    # Create agent
    if use_compression:
        agent, checkpointer = create_agent(
            use_compression=True,
            threshold=800,
            keep_recent=8
        )
    else:
        agent, checkpointer = create_agent(use_compression=False)

    config = {"configurable": {"thread_id": "long-convo-test"}}

    # System message
    agent.invoke({
        "messages": [
            SystemMessage(content="You are a helpful AI assistant. Keep responses concise (1-2 sentences).")
        ]
    }, config)

    # Generate questions
    questions = [
        "What is Python?",
        "Tell me about lists in Python.",
        "How do dictionaries work?",
        "Explain functions.",
        "What are classes?",
        "Tell me about inheritance.",
        "What is polymorphism?",
        "Explain decorators.",
        "What are generators?",
        "Tell me about context managers.",
    ] * (num_rounds // 10 + 1)
    questions = questions[:num_rounds]

    start_time = time.time()

    # Run conversation
    for i, question in enumerate(questions, start=1):
        if i % 5 == 0:
            print(f"  Round {i}/{num_rounds}...")

        response = agent.invoke({
            "messages": [HumanMessage(content=question)]
        }, config)

    elapsed_time = time.time() - start_time

    # Get stats
    if use_compression:
        stats = checkpointer.get_compression_stats()
        total_compressions = stats['total_compressions']
        tokens_before = stats['total_tokens_before']
        tokens_after = stats['total_tokens_after']
        token_reduction = stats['avg_token_reduction_percent']
    else:
        total_compressions = 0
        tokens_before = 0
        tokens_after = 0
        token_reduction = 0.0

    results = {
        "test": "long_conversation",
        "use_compression": use_compression,
        "rounds": num_rounds,
        "total_compressions": total_compressions,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "token_reduction_percent": token_reduction,
        "elapsed_time": round(elapsed_time, 2),
        "avg_time_per_round": round(elapsed_time / num_rounds, 3)
    }

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Rounds: {num_rounds}")
    print(f"  Compressions: {total_compressions}")
    if use_compression:
        print(f"  Tokens: {tokens_before} → {tokens_after} ({token_reduction:.1f}% reduction)")
    print(f"  Total time: {elapsed_time:.2f}s")
    print(f"  Avg time/round: {results['avg_time_per_round']:.3f}s")
    print(f"{'='*60}")

    return results


def test_comparison(num_rounds: int = 20) -> Dict[str, Any]:
    """Run side-by-side comparison: Baseline vs Compressed

    Args:
        num_rounds: Number of conversation rounds

    Returns:
        Comparison results
    """
    print(f"\n{'='*70}")
    print(f"COMPARISON TEST: Baseline vs Compressed ({num_rounds} rounds)")
    print(f"{'='*70}")

    # Run baseline
    print("\n[1/2] Running BASELINE (no compression)...")
    baseline_results = test_long_conversation(use_compression=False, num_rounds=num_rounds)

    # Run compressed
    print("\n[2/2] Running COMPRESSED...")
    compressed_results = test_long_conversation(use_compression=True, num_rounds=num_rounds)

    # Calculate improvements
    time_diff = baseline_results['elapsed_time'] - compressed_results['elapsed_time']
    time_change_pct = (time_diff / baseline_results['elapsed_time']) * 100

    comparison = {
        "test": "comparison",
        "num_rounds": num_rounds,
        "baseline": baseline_results,
        "compressed": compressed_results,
        "improvements": {
            "compressions": compressed_results['total_compressions'],
            "token_reduction_percent": compressed_results['token_reduction_percent'],
            "time_difference": round(time_diff, 2),
            "time_change_percent": round(time_change_pct, 2)
        }
    }

    print(f"\n{'='*70}")
    print(f"COMPARISON SUMMARY:")
    print(f"{'='*70}")
    print(f"Baseline:")
    print(f"  Time: {baseline_results['elapsed_time']:.2f}s")
    print(f"\nCompressed:")
    print(f"  Time: {compressed_results['elapsed_time']:.2f}s")
    print(f"  Compressions: {compressed_results['total_compressions']}")
    print(f"  Token reduction: {compressed_results['token_reduction_percent']:.1f}%")
    print(f"\nImpact:")
    print(f"  Time change: {time_diff:+.2f}s ({time_change_pct:+.1f}%)")
    print(f"{'='*70}")

    return comparison


# ============================================================================
# Main Benchmark Runner
# ============================================================================

def run_full_benchmark():
    """Run all benchmark tests and save results"""
    print("="*70)
    print("CONTEXT COMPRESSION BENCHMARK - PHASE 2")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set in environment")
        print("Please set it: export OPENAI_API_KEY='your-key-here'")
        return

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": []
    }

    # Test 1: Memory retention - Baseline
    print("\n" + "="*70)
    print("TEST 1/4: Memory Retention - Baseline")
    print("="*70)
    result1 = test_memory_retention(use_compression=False)
    all_results["tests"].append(result1)

    # Test 2: Memory retention - Compressed
    print("\n" + "="*70)
    print("TEST 2/4: Memory Retention - Compressed")
    print("="*70)
    result2 = test_memory_retention(use_compression=True)
    all_results["tests"].append(result2)

    # Test 3: Long conversation comparison
    print("\n" + "="*70)
    print("TEST 3/4: Long Conversation Comparison")
    print("="*70)
    result3 = test_comparison(num_rounds=30)
    all_results["tests"].append(result3)

    # Save results
    output_file = "benchmarks/benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"[SUCCESS] Benchmark completed!")
    print(f"Results saved to: {output_file}")
    print(f"{'='*70}")

    return all_results


if __name__ == "__main__":
    run_full_benchmark()
