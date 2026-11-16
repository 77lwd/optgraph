"""
Multi-Scenario Testing: Test memory system across different conversation patterns

Goal: Verify that 34.4% token savings is not just for one specific scenario
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
            # Estimate summarization cost
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


# ============================================================================
# Scenario 1: Short Conversation (5-10 rounds)
# ============================================================================

def scenario_1_short_conversation(agent, config):
    """Short conversation - may not trigger compression"""
    print("\n[Scenario 1] Short Conversation (10 rounds)")

    # Round 1: Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    # Rounds 2-9: Quick questions
    for i in range(2, 10):
        agent.invoke(
            {"messages": [("user", f"Quick question {i}: What's 2+2?")]},
            config
        )

    # Round 10: Recall test
    result = agent.invoke(
        {"messages": [("user", "What is my name and city?")]},
        config
    )

    return result


# ============================================================================
# Scenario 2: Medium Conversation (30 rounds) - Already tested in test_efficiency.py
# ============================================================================

def scenario_2_medium_conversation(agent, config):
    """Medium conversation - baseline scenario"""
    print("\n[Scenario 2] Medium Conversation (30 rounds)")

    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    for i in range(2, 31):
        agent.invoke(
            {"messages": [("user", f"Tell me about topic {i}.")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    return result


# ============================================================================
# Scenario 3: Long Conversation (100 rounds)
# ============================================================================

def scenario_3_long_conversation(agent, config):
    """Long conversation - test scalability"""
    print("\n[Scenario 3] Long Conversation (100 rounds)")

    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    for i in range(2, 101):
        agent.invoke(
            {"messages": [("user", f"Question {i}: Tell me something interesting.")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name, city, and hobby?")]},
        config
    )

    return result


# ============================================================================
# Scenario 4: Long Messages (20 rounds with long content)
# ============================================================================

def scenario_4_long_messages(agent, config):
    """Long message conversation - code/documents"""
    print("\n[Scenario 4] Long Messages (20 rounds)")

    # Round 1: Long introduction
    long_intro = (
        "Hi! My name is Alice, I'm a software engineer with 5 years of experience. "
        "I live in Beijing, China. I love Python programming, especially for data science "
        "and machine learning. I also enjoy JavaScript, TypeScript, and Go. "
        "In my free time, I contribute to open source projects and write technical blogs. "
        "I'm currently working on a project involving LangGraph and LLM applications. "
        "I'm interested in memory management, context compression, and efficient AI systems."
    )
    agent.invoke({"messages": [("user", long_intro)]}, config)

    # Rounds 2-20: Long questions (simulating code reviews, document analysis)
    for i in range(2, 21):
        long_message = (
            f"Question {i}: Can you help me analyze this code snippet? "
            "Here's what I'm working on: " + "x " * 100 +  # Padding to make it long
            f"The main issue I'm facing in iteration {i} is about performance optimization. "
            "I've tried several approaches but none seem to work efficiently. "
            "What would you recommend based on your experience?"
        )
        agent.invoke({"messages": [("user", long_message)]}, config)

    # Final recall
    result = agent.invoke(
        {"messages": [("user", "What do you know about me? My name, location, and skills?")]},
        config
    )

    return result


# ============================================================================
# Scenario 5: Mixed Realistic Conversation
# ============================================================================

def scenario_5_realistic_conversation(agent, config):
    """Realistic mixed conversation - tech Q&A"""
    print("\n[Scenario 5] Realistic Mixed Conversation (30 rounds)")

    # Introduction
    agent.invoke(
        {"messages": [("user", "Hi! I'm Alice from Beijing. I'm working with Python and LangGraph.")]},
        config
    )

    # Mix of short and long messages
    realistic_questions = [
        "What's LangGraph?",
        "How do I create a state graph? Please explain in detail with the key concepts.",
        "Thanks!",
        "Now, can you show me an example? Here's my current code: " + "code " * 50,
        "I see. What about checkpointers?",
        "I'm getting an error: 'RemoveMessage not found'. " + "error " * 30 + " How do I fix this?",
        "That worked!",
        "Next question: how do I optimize memory usage in long conversations?",
        "Can you explain the difference between State layer and Checkpointer layer?",
        "Interesting. What about compression strategies?",
    ]

    # Repeat pattern 3 times to get to 30 rounds
    for round_num in range(3):
        for i, question in enumerate(realistic_questions):
            agent.invoke({"messages": [("user", question)]}, config)

    # Final recall
    result = agent.invoke(
        {"messages": [("user", "Remind me, what's my name and where am I from?")]},
        config
    )

    return result


# ============================================================================
# Main Test Runner
# ============================================================================

def run_scenario(scenario_func, scenario_name, llm_config):
    """Run one scenario with baseline vs compression"""
    print("\n" + "="*70)
    print(f"Testing: {scenario_name}")
    print("="*70)

    # Baseline
    print("\n[Baseline] No compression")
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"baseline-{scenario_name}-{int(time.time()*1000)}"}}

    start_time = time.time()
    baseline_result = scenario_func(baseline_agent, baseline_config)
    baseline_time = time.time() - start_time

    baseline_stats = baseline_tracker.get_stats()

    # Memory compression
    print("\n[Memory] With compression")
    memory_agent, memory_tracker = create_memory_agent(llm_config)
    memory_config = {"configurable": {"thread_id": f"memory-{scenario_name}-{int(time.time()*1000)}"}}

    start_time = time.time()
    memory_result = scenario_func(memory_agent, memory_config)
    memory_time = time.time() - start_time

    memory_stats = memory_tracker.get_stats()

    # Calculate metrics
    token_reduction = ((baseline_stats['total_tokens'] - memory_stats['total_tokens'])
                       / baseline_stats['total_tokens'] * 100) if baseline_stats['total_tokens'] > 0 else 0

    time_overhead = ((memory_time - baseline_time) / baseline_time * 100) if baseline_time > 0 else 0

    # Check quality
    baseline_response = baseline_result['messages'][-1].content.lower()
    memory_response = memory_result['messages'][-1].content.lower()

    baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response)) / 2.0 * 100
    memory_quality = (('alice' in memory_response) + ('beijing' in memory_response)) / 2.0 * 100

    # Print results
    print("\n" + "-"*70)
    print("RESULTS:")
    print("-"*70)
    print(f"Baseline:  {baseline_stats['total_tokens']:,} tokens, {baseline_time:.1f}s, Quality: {baseline_quality:.0f}%")
    print(f"Memory:    {memory_stats['total_tokens']:,} tokens, {memory_time:.1f}s, Quality: {memory_quality:.0f}%")
    print(f"Savings:   {token_reduction:+.1f}% tokens, {time_overhead:+.1f}% time")
    print("-"*70)

    return {
        'scenario': scenario_name,
        'baseline_tokens': baseline_stats['total_tokens'],
        'memory_tokens': memory_stats['total_tokens'],
        'token_reduction': token_reduction,
        'baseline_time': baseline_time,
        'memory_time': memory_time,
        'time_overhead': time_overhead,
        'baseline_quality': baseline_quality,
        'memory_quality': memory_quality,
    }


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Multi-Scenario Memory System Testing")
    print("="*70)
    print("\nGoal: Verify token savings across different conversation patterns")
    print("Current known result: 34.4% savings in medium conversation (30 rounds)")
    print("\nTesting 5 scenarios...")

    results = []

    # Run all scenarios
    results.append(run_scenario(scenario_1_short_conversation, "Short Conversation (10 rounds)", llm_config))
    results.append(run_scenario(scenario_2_medium_conversation, "Medium Conversation (30 rounds)", llm_config))
    results.append(run_scenario(scenario_3_long_conversation, "Long Conversation (100 rounds)", llm_config))
    results.append(run_scenario(scenario_4_long_messages, "Long Messages (20 rounds)", llm_config))
    results.append(run_scenario(scenario_5_realistic_conversation, "Realistic Mixed (30 rounds)", llm_config))

    # Summary table
    print("\n" + "="*70)
    print("SUMMARY: Token Savings Across Scenarios")
    print("="*70)
    print(f"{'Scenario':<35} {'Token Reduction':>15} {'Quality':>10}")
    print("-"*70)

    for r in results:
        print(f"{r['scenario']:<35} {r['token_reduction']:>14.1f}% {r['memory_quality']:>9.0f}%")

    # Statistics
    reductions = [r['token_reduction'] for r in results]
    avg_reduction = sum(reductions) / len(reductions)
    min_reduction = min(reductions)
    max_reduction = max(reductions)

    print("-"*70)
    print(f"{'Average':<35} {avg_reduction:>14.1f}%")
    print(f"{'Range':<35} {min_reduction:.1f}% - {max_reduction:.1f}%")
    print("="*70)

    print("\nConclusion:")
    print(f"  Token savings range: {min_reduction:.1f}% - {max_reduction:.1f}%")
    print(f"  Average savings: {avg_reduction:.1f}%")
    print(f"  All scenarios maintain quality: {all(r['memory_quality'] >= 90 for r in results)}")


if __name__ == "__main__":
    main()
