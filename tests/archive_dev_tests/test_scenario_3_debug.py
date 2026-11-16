"""
Debug Scenario 3: Detailed token breakdown per round

Purpose: Find the real overhead source
"""

import sys
sys.path.insert(0, '.')

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from optgraph.memory_state import MemoryState, should_compress, compress_memory, get_context_with_memory
from optgraph.token_tracker import TokenTracker


def create_agent(llm_config):
    """Create agent with detailed logging"""

    llm = ChatOpenAI(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        temperature=llm_config["temperature"]
    )

    tracker = TokenTracker()

    def chatbot_node(state: MemoryState):
        # Get context with memory
        messages = get_context_with_memory(state)

        print(f"\n[Round] Messages in context: {len(messages)}")

        # Estimate tokens
        context_tokens = sum(len(str(m.content)) for m in messages) // 4
        print(f"[Round] Estimated context tokens: {context_tokens}")

        # Call LLM
        response = llm.invoke(messages)
        tracker.record_usage(response)

        return {"messages": [response]}

    def memory_node(state: MemoryState):
        if should_compress(state, max_messages=20):
            print(f"\n[Compression] Triggered at {len(state['messages'])} messages")
            updates = compress_memory(state, llm, keep_recent=10)

            if updates:
                # Count deleted messages
                deleted = sum(1 for msg in updates.get("messages", [])
                             if hasattr(msg, '__class__') and 'Remove' in msg.__class__.__name__)
                print(f"[Compression] Deleted {deleted} messages")

            return updates
        return {}

    # Build graph
    builder = StateGraph(MemoryState)
    builder.add_node("chatbot", chatbot_node)
    builder.add_node("memory", memory_node)

    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", "memory")
    builder.add_edge("memory", END)

    checkpointer = MemorySaver()
    agent = builder.compile(checkpointer=checkpointer)

    return agent, tracker


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("=" * 60)
    print("Scenario 3 Debug: Detailed Token Breakdown")
    print("=" * 60)

    agent, tracker = create_agent(llm_config)
    config = {"configurable": {"thread_id": "scenario_3_debug"}}

    # Track per-round tokens
    round_data = []

    # Round 1
    print("\n" + "=" * 60)
    print("ROUND 1: Introduction")
    print("=" * 60)
    before = tracker.get_stats()
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice.")]},
        config
    )
    after = tracker.get_stats()
    tokens_used = after["total_tokens"] - before["total_tokens"]
    round_data.append({"round": 1, "tokens": tokens_used})
    print(f"[Result] Tokens used: {tokens_used}")

    # Rounds 2-25 (shortened for debug)
    for i in range(2, 26):
        print("\n" + "=" * 60)
        print(f"ROUND {i}")
        print("=" * 60)
        before = tracker.get_stats()
        agent.invoke(
            {"messages": [("user", f"Question {i}")]},
            config
        )
        after = tracker.get_stats()
        tokens_used = after["total_tokens"] - before["total_tokens"]
        round_data.append({"round": i, "tokens": tokens_used})
        print(f"[Result] Tokens used: {tokens_used}")

    # Analysis
    print("\n" + "=" * 60)
    print("TOKEN USAGE ANALYSIS")
    print("=" * 60)

    for i, data in enumerate(round_data):
        print(f"Round {data['round']:2d}: {data['tokens']:5d} tokens")

        # Highlight compression rounds
        if i > 0 and data['tokens'] > round_data[i-1]['tokens'] * 1.5:
            print("           ^^^ SPIKE - Likely compression overhead")

    print("\n" + "=" * 60)
    print(f"Total tokens: {tracker.get_stats()['total_tokens']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
