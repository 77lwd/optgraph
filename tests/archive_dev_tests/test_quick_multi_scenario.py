"""
Quick Multi-Scenario Test - Only 2 scenarios for fast validation
"""

import sys
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


def scenario_short_conversation(agent, config):
    """Short conversation - 10 rounds"""
    sys.stdout.write("  Running 10 rounds...")
    sys.stdout.flush()

    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    for i in range(2, 10):
        agent.invoke(
            {"messages": [("user", f"Quick question {i}")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "What is my name and city?")]},
        config
    )

    sys.stdout.write(" Done!\n")
    sys.stdout.flush()
    return result


def scenario_long_messages(agent, config):
    """Long messages - 15 rounds"""
    sys.stdout.write("  Running 15 rounds with long messages...")
    sys.stdout.flush()

    long_intro = (
        "Hi! My name is Alice, I'm a software engineer with 5 years of experience. "
        "I live in Beijing, China. I love Python programming, especially for data science. "
        * 3  # Repeat to make it longer
    )
    agent.invoke({"messages": [("user", long_intro)]}, config)

    for i in range(2, 15):
        long_message = f"Question {i}: " + "Please help me with this issue. " * 20
        agent.invoke({"messages": [("user", long_message)]}, config)

    result = agent.invoke(
        {"messages": [("user", "What do you know about me?")]},
        config
    )

    sys.stdout.write(" Done!\n")
    sys.stdout.flush()
    return result


def run_scenario(scenario_func, scenario_name, llm_config):
    """Run one scenario"""
    print("\n" + "="*70)
    print(f"{scenario_name}")
    print("="*70)

    # Baseline
    print("\n[Baseline] No compression")
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"b-{int(time.time()*1000)}"}}

    start = time.time()
    baseline_result = scenario_func(baseline_agent, baseline_config)
    baseline_time = time.time() - start
    baseline_stats = baseline_tracker.get_stats()

    # Memory
    print("\n[Memory] With compression")
    memory_agent, memory_tracker = create_memory_agent(llm_config)
    memory_config = {"configurable": {"thread_id": f"m-{int(time.time()*1000)}"}}

    start = time.time()
    memory_result = scenario_func(memory_agent, memory_config)
    memory_time = time.time() - start
    memory_stats = memory_tracker.get_stats()

    # Results
    token_reduction = ((baseline_stats['total_tokens'] - memory_stats['total_tokens'])
                       / baseline_stats['total_tokens'] * 100) if baseline_stats['total_tokens'] > 0 else 0

    baseline_resp = baseline_result['messages'][-1].content.lower()
    memory_resp = memory_result['messages'][-1].content.lower()

    baseline_q = (('alice' in baseline_resp) + ('beijing' in baseline_resp)) / 2.0 * 100
    memory_q = (('alice' in memory_resp) + ('beijing' in memory_resp)) / 2.0 * 100

    print("\n" + "-"*70)
    print("RESULTS:")
    print(f"  Baseline:  {baseline_stats['total_tokens']:,} tokens, {baseline_time:.1f}s, Quality: {baseline_q:.0f}%")
    print(f"  Memory:    {memory_stats['total_tokens']:,} tokens, {memory_time:.1f}s, Quality: {memory_q:.0f}%")
    print(f"  Savings:   {token_reduction:+.1f}% tokens")
    print("-"*70)

    return {
        'scenario': scenario_name,
        'token_reduction': token_reduction,
        'baseline_quality': baseline_q,
        'memory_quality': memory_q,
    }


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Quick Multi-Scenario Test (2 scenarios)")
    print("="*70)

    results = []
    results.append(run_scenario(scenario_short_conversation, "Scenario 1: Short (10 rounds)", llm_config))
    results.append(run_scenario(scenario_long_messages, "Scenario 2: Long Messages (15 rounds)", llm_config))

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for r in results:
        print(f"{r['scenario']:<45} {r['token_reduction']:>8.1f}% | Quality: {r['memory_quality']:.0f}%")

    avg = sum(r['token_reduction'] for r in results) / len(results)
    print("-"*70)
    print(f"{'Average':<45} {avg:>8.1f}%")
    print("="*70)


if __name__ == "__main__":
    main()
