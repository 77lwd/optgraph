"""
Example: Chat agent with memory management

Shows how to use the new memory system based on industry best practices.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from optgraph.memory_state import (
    MemoryState,
    should_compress,
    compress_memory,
    get_context_with_memory
)


def create_chat_agent_with_memory(
    llm_config: dict,
    max_messages: int = 20,
    keep_recent: int = 10
):
    """Create a chat agent with memory management

    Args:
        llm_config: LLM configuration (model, api_key, base_url, temperature)
        max_messages: Trigger compression when messages exceed this
        keep_recent: Number of recent messages to keep after compression

    Returns:
        Compiled graph with checkpointer
    """

    # Create LLMs
    main_llm = ChatOpenAI(**llm_config)

    # Summarizer with lower temperature for consistency
    summarizer_config = llm_config.copy()
    summarizer_config["temperature"] = 0.3
    summarizer_llm = ChatOpenAI(**summarizer_config)

    # Define nodes
    def chat_node(state: MemoryState):
        """Main chat node - calls LLM with full context"""

        # Get messages with memory context
        messages = get_context_with_memory(state)

        # Debug: print what we're sending to LLM
        print(f"\n[chat_node] Sending {len(messages)} messages to LLM:")
        for i, msg in enumerate(messages):
            content_preview = str(msg.content)[:150] if len(str(msg.content)) > 150 else str(msg.content)
            print(f"  [{i+1}] {msg.type}: {content_preview}")

        # Call LLM
        response = main_llm.invoke(messages)

        return {"messages": [response]}

    def memory_check_node(state: MemoryState):
        """Check if compression is needed"""
        return {"_should_compress": should_compress(state, max_messages)}

    def compress_node(state: MemoryState):
        """Compress memory when needed"""
        return compress_memory(state, summarizer_llm, keep_recent)

    # Build graph
    def route_after_chat(state: MemoryState):
        """Route to compression or end based on message count"""
        if should_compress(state, max_messages):
            return "compress"
        else:
            return END

    builder = StateGraph(MemoryState)

    # Add nodes
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)

    # Add edges
    builder.add_edge(START, "chat")
    builder.add_conditional_edges(
        "chat",
        route_after_chat,
        {
            "compress": "compress",
            END: END
        }
    )
    builder.add_edge("compress", END)

    # Compile with checkpointer
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    return graph


# Example usage
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
    agent = create_chat_agent_with_memory(
        llm_config=llm_config,
        max_messages=10,  # Compress after 10 messages
        keep_recent=5     # Keep 5 recent messages
    )

    # Test conversation
    thread_id = f"test-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    print("="*70)
    print("Chat Agent with Memory Management")
    print("="*70)

    # Round 1: User introduces themselves
    print("\n[Round 1] User introduces themselves...")
    result = agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )
    print(f"Agent: {result['messages'][-1].content}")

    # Rounds 2-12: Filler conversation to trigger compression
    print("\n[Rounds 2-12] Filler conversation...")
    for i in range(2, 13):
        result = agent.invoke(
            {"messages": [("user", f"Tell me something interesting about topic {i}.")]},
            config
        )
        if i % 3 == 0:
            print(f"  [Round {i}] Message count: {len(result.get('messages', []))}")

    # Round 13: Test recall
    print("\n[Round 13] Testing recall...")
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content
    print(f"\nAgent's response:\n{response}")

    # Check quality
    print("\n" + "="*70)
    print("Quality Check:")
    response_lower = response.lower()
    has_alice = 'alice' in response_lower
    has_beijing = 'beijing' in response_lower
    has_python = 'python' in response_lower

    print(f"  Contains 'Alice': {has_alice}")
    print(f"  Contains 'Beijing': {has_beijing}")
    print(f"  Contains 'Python': {has_python}")
    print(f"  Quality: {(has_alice + has_beijing + has_python) / 3.0 * 100:.1f}%")

    # Show state
    print("\n" + "="*70)
    print("Final State:")
    print(f"  Messages: {len(result.get('messages', []))}")
    print(f"  Summary: {result.get('summary', 'None')[:100]}...")
    print(f"  User Profile: {result.get('user_profile', {})}")
    print("="*70)
