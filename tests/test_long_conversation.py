"""
Long Conversation Test: Test quality retention over 50 rounds
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


def create_agent(llm_config, max_messages=20, keep_recent=10):
    """Create chat agent"""
    main_llm = ChatOpenAI(**llm_config)

    summarizer_config = llm_config.copy()
    summarizer_config["temperature"] = 0.3
    summarizer_llm = ChatOpenAI(**summarizer_config)

    def chat_node(state: MemoryState):
        messages = get_context_with_memory(state)
        response = main_llm.invoke(messages)
        return {"messages": [response]}

    def compress_node(state: MemoryState):
        result = compress_memory(state, summarizer_llm, keep_recent)
        # Track compression stats
        if result:
            print(f"    [Compression triggered] Messages: {len(state.get('messages', []))} → {keep_recent}")
        return result

    def route_after_chat(state: MemoryState):
        return "compress" if should_compress(state, max_messages) else END

    builder = StateGraph(MemoryState)
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", route_after_chat, {"compress": "compress", END: END})
    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver())


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Long Conversation Test: 50 rounds")
    print("="*70)
    print("Config: max_messages=20, keep_recent=10")
    print()

    agent = create_agent(llm_config, max_messages=20, keep_recent=10)

    thread_id = f"long-test-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: User introduces themselves
    print("[Round 1] User introduces themselves...")
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-49: Filler
    print("\n[Rounds 2-49] Filler conversation...")
    for i in range(2, 50):
        agent.invoke(
            {"messages": [("user", f"Tell me an interesting fact about topic {i}.")]},
            config
        )
        if i % 10 == 0:
            print(f"  [Round {i}] Progress...")

    # Round 50: Test recall
    print("\n[Round 50] Testing recall...")
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content
    print(f"\nAgent's response:\n{response}")

    # Check quality
    print("\n" + "="*70)
    print("Quality Check")
    print("="*70)
    response_lower = response.lower()
    has_alice = 'alice' in response_lower
    has_beijing = 'beijing' in response_lower
    has_python = 'python' in response_lower

    print(f"  Contains 'Alice': {has_alice}")
    print(f"  Contains 'Beijing': {has_beijing}")
    print(f"  Contains 'Python': {has_python}")
    quality = (has_alice + has_beijing + has_python) / 3.0 * 100
    print(f"  Quality: {quality:.1f}%")

    # Show final state
    print("\n" + "="*70)
    print("Final State")
    print("="*70)
    print(f"  Messages: {len(result.get('messages', []))}")
    print(f"  Summary: {result.get('summary', 'None')[:150]}...")
    print(f"  User Profile: {result.get('user_profile', {})}")

    print("\n" + "="*70)
    if quality == 100.0:
        print("[OK] SUCCESS: 100% quality after 50 rounds")
    else:
        print(f"[WARN]  PARTIAL: {quality:.1f}% quality after 50 rounds")
    print("="*70)


if __name__ == "__main__":
    main()
