"""
Efficiency Comparison: New memory system vs No compression baseline
"""

import time
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
    """Baseline: No compression, keep all messages"""
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
    """New approach: With memory compression"""
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
        # Track summarization cost
        if result:
            # Summarization also uses tokens
            tracker.record_request(input_tokens=200, output_tokens=50)  # Estimate
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


def run_conversation(agent, config, rounds=30):
    """Run a conversation"""
    # Round 1
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Filler rounds
    for i in range(2, rounds + 1):
        agent.invoke(
            {"messages": [("user", f"Tell me a fact about topic {i}.")]},
            config
        )

    # Final recall test
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    return result


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    rounds = 30

    print("="*70)
    print(f"Efficiency Comparison: {rounds} rounds")
    print("="*70)

    # Test 1: Baseline (no compression)
    print("\n[Test 1] Baseline: No compression")
    print("-" * 70)
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"baseline-{int(time.time()*1000)}"}}

    start_time = time.time()
    baseline_result = run_conversation(baseline_agent, baseline_config, rounds)
    baseline_time = time.time() - start_time

    baseline_stats = baseline_tracker.get_stats()
    print(f"  Time: {baseline_time:.2f}s")
    print(f"  Total tokens: {baseline_stats['total_tokens']:,}")
    print(f"  Total requests: {baseline_stats['total_requests']}")
    print(f"  Avg tokens/request: {baseline_stats['avg_tokens_per_request']:.0f}")

    # Check quality
    baseline_response = baseline_result['messages'][-1].content.lower()
    baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response) + ('python' in baseline_response)) / 3.0 * 100
    print(f"  Quality: {baseline_quality:.1f}%")

    # Test 2: With memory compression
    print("\n[Test 2] With Memory Compression")
    print("-" * 70)
    memory_agent, memory_tracker = create_memory_agent(llm_config, max_messages=20, keep_recent=10)
    memory_config = {"configurable": {"thread_id": f"memory-{int(time.time()*1000)}"}}

    start_time = time.time()
    memory_result = run_conversation(memory_agent, memory_config, rounds)
    memory_time = time.time() - start_time

    memory_stats = memory_tracker.get_stats()
    print(f"  Time: {memory_time:.2f}s")
    print(f"  Total tokens: {memory_stats['total_tokens']:,}")
    print(f"  Total requests: {memory_stats['total_requests']}")
    print(f"  Avg tokens/request: {memory_stats['avg_tokens_per_request']:.0f}")

    # Check quality
    memory_response = memory_result['messages'][-1].content.lower()
    memory_quality = (('alice' in memory_response) + ('beijing' in memory_response) + ('python' in memory_response)) / 3.0 * 100
    print(f"  Quality: {memory_quality:.1f}%")

    # Comparison
    print("\n" + "="*70)
    print("Comparison")
    print("="*70)

    token_savings = (baseline_stats['total_tokens'] - memory_stats['total_tokens']) / baseline_stats['total_tokens'] * 100
    time_diff = (memory_time - baseline_time) / baseline_time * 100

    print(f"Token savings: {token_savings:+.1f}%")
    print(f"Time difference: {time_diff:+.1f}%")
    print(f"Quality difference: {memory_quality - baseline_quality:+.1f}%")

    print("\n" + "="*70)
    if memory_quality >= 90 and token_savings > 0:
        print(f"[OK] SUCCESS: {token_savings:.1f}% token savings with {memory_quality:.0f}% quality")
    elif memory_quality >= 90:
        print(f"[WARN]  Quality OK ({memory_quality:.0f}%) but no token savings ({token_savings:.1f}%)")
    else:
        print(f"[FAIL] FAIL: Quality dropped to {memory_quality:.0f}%")
    print("="*70)


if __name__ == "__main__":
    main()
