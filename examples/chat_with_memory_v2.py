"""
Example: Chat agent with Memory System v2.0

Key differences from v1:
1. Memory NOT passed to LLM by default (zero overhead)
2. Only injected when user asks to recall
3. Structured storage instead of natural language summary
"""

from langgraph.graph import StateGraph, START, END
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


def create_chat_agent_v2(llm_config, max_messages=20, keep_recent=10):
    """
    Create chat agent with Memory v2.0

    Architecture:
    - chat_node: Normal chat (no memory, zero overhead)
    - recall_node: Chat with memory retrieval (when needed)
    - compress_node: Compress old messages to structured storage

    Default path: START -> chat_node -> END (zero memory overhead)
    Recall path: START -> recall_node -> END (controlled overhead)
    """

    # Create LLMs
    main_llm = ChatOpenAI(**llm_config)

    # Compressor LLM (for extracting structured data)
    compressor_config = llm_config.copy()
    compressor_config["temperature"] = 0.3
    compressor_llm = ChatOpenAI(**compressor_config)

    compressor = MemoryCompressor(compressor_llm)

    # === Node Definitions ===

    def chat_node(state: MemoryStateV2):
        """
        Main chat node - NO memory overhead

        This is the default path (90% of conversations)
        Only uses recent messages, no memory injection
        """
        # Get baseline context (no memory)
        messages = get_context_baseline(state)

        print(f"\n[chat_node] Using baseline context: {len(messages)} messages (NO memory)")

        # Call LLM
        response = main_llm.invoke(messages)

        return {"messages": [response]}

    def recall_node(state: MemoryStateV2):
        """
        Recall node - WITH memory retrieval

        This is only called when user explicitly needs memory (10% of conversations)
        Retrieves relevant facts and injects into context
        """
        # Get last user message
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        query = str(last_message.content)

        # Get context with memory retrieval
        messages_with_memory = get_context_with_recall(state, query, top_k=3)

        print(f"\n[recall_node] Using context with memory: {len(messages_with_memory)} messages (WITH memory)")

        # Call LLM
        response = main_llm.invoke(messages_with_memory)

        return {"messages": [response]}

    def compress_node(state: MemoryStateV2):
        """
        Compress node - Extract structured data from old messages
        """
        print(f"\n[compress_node] Triggered")
        return compress_memory_v2(state, compressor, keep_recent)

    # === Routing Logic ===

    def route_entry(state: MemoryStateV2):
        """
        Entry router: decide if recall is needed

        This is the key decision point:
        - Recall needed? -> recall_node (has overhead)
        - No recall? -> chat_node (zero overhead)
        """
        messages = state.get("messages", [])
        if not messages:
            return "chat"

        last_message = messages[-1]
        user_message = str(last_message.content)

        if needs_recall(user_message):
            print(f"[Router] RECALL needed (detected keywords)")
            return "recall"
        else:
            print(f"[Router] NO recall needed (baseline path)")
            return "chat"

    def route_after_chat(state: MemoryStateV2):
        """Route to compression or end"""
        if should_compress_v2(state, max_messages):
            return "compress"
        return END

    # === Build Graph ===

    builder = StateGraph(MemoryStateV2)

    # Add nodes
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

    # After chat: check compression
    builder.add_conditional_edges(
        "chat",
        route_after_chat,
        {
            "compress": "compress",
            END: END
        }
    )

    # After recall: check compression
    builder.add_conditional_edges(
        "recall",
        route_after_chat,
        {
            "compress": "compress",
            END: END
        }
    )

    # After compress: end
    builder.add_edge("compress", END)

    # Compile
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    return graph


# === Demo ===

if __name__ == "__main__":
    import time

    # Configuration
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    # Create agent
    agent = create_chat_agent_v2(
        llm_config=llm_config,
        max_messages=20,  # Compress after 20 messages
        keep_recent=10     # Keep 10 recent messages
    )

    # Test conversation
    thread_id = f"test-v2-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    print("="*70)
    print("Chat Agent with Memory System v2.0")
    print("="*70)
    print("\nKey features:")
    print("- Default: NO memory overhead (zero tokens)")
    print("- Only inject memory when user asks to recall")
    print("- Structured storage (not natural language summary)")
    print("="*70)

    # Round 1: User introduces themselves
    print("\n[Round 1] User introduces themselves...")
    result = agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )
    print(f"Agent: {result['messages'][-1].content[:200]}")

    # Rounds 2-12: Regular chat (NO memory overhead)
    print("\n[Rounds 2-12] Regular chat (should use baseline path)...")
    for i in range(2, 13):
        print(f"\n--- Round {i} ---")
        result = agent.invoke(
            {"messages": [("user", f"Tell me something interesting about topic {i}.")]},
            config
        )

    # Check state
    print(f"\n[After Round 12] Message count: {len(result.get('messages', []))}")
    print(f"[After Round 12] Has structured_memory: {bool(result.get('structured_memory'))}")
    if result.get('structured_memory'):
        memory = result['structured_memory']
        print(f"[After Round 12] User profile: {memory.get('user_profile', {})}")
        print(f"[After Round 12] Key facts: {len(memory.get('key_facts', []))}")

    # Rounds 13-15: More regular chat
    print("\n[Rounds 13-15] More regular chat...")
    for i in range(13, 16):
        print(f"\n--- Round {i} ---")
        result = agent.invoke(
            {"messages": [("user", f"Question {i}: What do you think?")]},
            config
        )

    # Round 16: Test recall (should trigger recall path)
    print("\n[Round 16] Testing RECALL (should trigger recall path)...")
    print("User asks: 'Remind me: what is my name, city, and hobby?'")
    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content
    print(f"\nAgent's response:\n{response}")

    # Quality check
    print("\n" + "="*70)
    print("Quality Check:")
    response_lower = response.lower()
    has_alice = 'alice' in response_lower
    has_beijing = 'beijing' in response_lower
    has_python = 'python' in response_lower

    print(f"  Contains 'Alice': {has_alice}")
    print(f"  Contains 'Beijing': {has_beijing}")
    print(f"  Contains 'Python': {has_python}")
    quality = (has_alice + has_beijing + has_python) / 3.0 * 100
    print(f"  Quality: {quality:.1f}%")

    # Final state
    print("\n" + "="*70)
    print("Final State:")
    print(f"  Messages: {len(result.get('messages', []))}")

    if result.get('structured_memory'):
        memory = result['structured_memory']
        print(f"  User Profile: {memory.get('user_profile', {})}")
        print(f"  Key Facts: {len(memory.get('key_facts', []))}")
        for fact in memory.get('key_facts', [])[:3]:
            print(f"    - Round {fact['round']}: {fact['fact'][:60]}...")
        print(f"  Topic Threads: {list(memory.get('topic_threads', {}).keys())}")
    else:
        print(f"  Structured Memory: None yet")

    print("="*70)

    # Round 17-22: More baseline chat to verify zero overhead continues
    print("\n[Rounds 17-22] More baseline chat to verify zero overhead...")
    for i in range(17, 23):
        result = agent.invoke(
            {"messages": [("user", f"Random question {i}")]},
            config
        )

    print(f"\n[After Round 22] Message count: {len(result.get('messages', []))}")

    # Round 23: Another recall test
    print("\n[Round 23] Another recall test...")
    result = agent.invoke(
        {"messages": [("user", "What did we discuss earlier?")]},
        config
    )
    print(f"Agent: {result['messages'][-1].content[:300]}")

    print("\n" + "="*70)
    print("Demo completed!")
    print("="*70)
