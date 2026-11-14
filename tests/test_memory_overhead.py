"""
Memory Overhead Analysis: Compare message counts and context size

Tests whether fake conversation injection increases memory overhead significantly.
"""

import time
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from optgraph.memory_state import (
    MemoryState,
    should_compress,
    compress_memory,
    get_context_with_memory
)


def count_tokens_estimate(text):
    """Rough token count estimate (4 chars ≈ 1 token)"""
    if isinstance(text, int):
        return text
    return len(str(text)) // 4


def create_agent(llm_config, max_messages=20, keep_recent=10):
    """Create chat agent with tracking"""
    main_llm = ChatOpenAI(**llm_config)

    summarizer_config = llm_config.copy()
    summarizer_config["temperature"] = 0.3
    summarizer_llm = ChatOpenAI(**summarizer_config)

    context_sizes = []

    def chat_node(state: MemoryState):
        messages = get_context_with_memory(state)

        # Track context size
        total_chars = sum(len(str(m.content)) for m in messages)
        estimated_tokens = count_tokens_estimate(total_chars)
        context_sizes.append({
            "message_count": len(messages),
            "total_chars": total_chars,
            "estimated_tokens": estimated_tokens
        })

        response = main_llm.invoke(messages)
        return {"messages": [response]}

    def compress_node(state: MemoryState):
        return compress_memory(state, summarizer_llm, keep_recent)

    def route_after_chat(state: MemoryState):
        return "compress" if should_compress(state, max_messages) else END

    builder = StateGraph(MemoryState)
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", route_after_chat, {"compress": "compress", END: END})
    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver()), context_sizes


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Memory Overhead Analysis")
    print("="*70)

    agent, context_sizes = create_agent(llm_config, max_messages=20, keep_recent=10)

    thread_id = f"overhead-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    rounds = 30

    # Round 1
    print(f"\nRunning {rounds} rounds...")
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Filler rounds
    for i in range(2, rounds + 1):
        agent.invoke(
            {"messages": [("user", f"Tell me an interesting fact about topic {i}.")]},
            config
        )

    # Analysis
    print("\n" + "="*70)
    print("Context Size Over Time")
    print("="*70)

    print(f"\n{'Round':<10} {'Messages':<12} {'Est. Tokens':<15} {'Notes'}")
    print("-" * 70)

    for i, ctx in enumerate(context_sizes, 1):
        notes = ""
        if i == 1:
            notes = "Initial"
        elif i > 1 and ctx['message_count'] < context_sizes[i-2]['message_count']:
            notes = "[WARN] Compression"

        # Print every 5 rounds or when compression happens
        if i % 5 == 0 or notes:
            print(f"{i:<10} {ctx['message_count']:<12} {ctx['estimated_tokens']:<15,} {notes}")

    # Statistics
    print("\n" + "="*70)
    print("Statistics")
    print("="*70)

    avg_messages = sum(c['message_count'] for c in context_sizes) / len(context_sizes)
    avg_tokens = sum(c['estimated_tokens'] for c in context_sizes) / len(context_sizes)
    max_messages = max(c['message_count'] for c in context_sizes)
    max_tokens = max(c['estimated_tokens'] for c in context_sizes)
    min_messages = min(c['message_count'] for c in context_sizes)
    min_tokens = min(c['estimated_tokens'] for c in context_sizes)

    print(f"Average messages per request: {avg_messages:.1f}")
    print(f"Average tokens per request: {avg_tokens:,.0f}")
    print(f"Max messages: {max_messages}")
    print(f"Max tokens: {max_tokens:,}")
    print(f"Min messages (after compression): {min_messages}")
    print(f"Min tokens (after compression): {min_tokens:,}")

    # Overhead from fake conversation
    fake_convo_overhead = 2  # 2 messages (HumanMessage + AIMessage for profile)
    fake_convo_tokens = count_tokens_estimate("Hi! my name is Alice, and I live in Beijing, and I love Python.Got it! I'll remember that.")

    print("\n" + "="*70)
    print("Fake Conversation Overhead")
    print("="*70)
    print(f"Extra messages injected: {fake_convo_overhead}")
    print(f"Extra tokens per request: ~{fake_convo_tokens}")
    print(f"Percentage overhead: {fake_convo_tokens / avg_tokens * 100:.1f}% of average context")

    print("\n" + "="*70)
    if fake_convo_tokens / avg_tokens < 0.1:
        print(f"[OK] LOW overhead: Fake conversation adds only ~{fake_convo_tokens / avg_tokens * 100:.1f}% to context")
    elif fake_convo_tokens / avg_tokens < 0.2:
        print(f"[WARN]  MODERATE overhead: Fake conversation adds ~{fake_convo_tokens / avg_tokens * 100:.1f}% to context")
    else:
        print(f"[FAIL] HIGH overhead: Fake conversation adds ~{fake_convo_tokens / avg_tokens * 100:.1f}% to context")
    print("="*70)


if __name__ == "__main__":
    main()
