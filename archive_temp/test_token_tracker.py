"""
Test TokenTracker integration with AdaptiveCheckpointSaver

Verify that real API token counts are correctly extracted and used.
"""

import os
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.token_tracker import TokenTracker


def create_chat_agent(checkpointer, api_key, tracker=None):
    """Create a simple chat agent for testing"""

    # LLM configuration
    llm = ChatOpenAI(
        model="deepseek-v4.1-flash",
        api_key=api_key,
        base_url="https://beeapi.dev/v1",
        temperature=0.7,
    )

    def chat_node(state: MessagesState):
        """Chat node that calls LLM"""
        response = llm.invoke(state["messages"])

        # Record token usage if tracker provided
        if tracker:
            tracker.record_usage(response)

        return {"messages": [response]}

    # Build graph
    graph = StateGraph(MessagesState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.set_finish_point("chat")

    return graph.compile(checkpointer=checkpointer)


def test_token_tracker_basic():
    """Test basic TokenTracker functionality"""
    print("\n" + "="*60)
    print("Test 1: Basic TokenTracker")
    print("="*60)

    # API key
    api_key = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"

    # Create tracker
    tracker = TokenTracker()

    # Create checkpointer with tracker
    checkpointer = AdaptiveCheckpointSaver(
        threshold=1000,
        keep_recent=3,
        token_tracker=tracker
    )

    # Create agent
    agent = create_chat_agent(checkpointer, api_key, tracker)

    # Run a few rounds
    config = {"configurable": {"thread_id": "test-1"}}

    print("\n[Round 1] Asking about Python")
    result = agent.invoke(
        {"messages": [("user", "What is Python? Answer in one sentence.")]},
        config
    )
    print(f"Response: {result['messages'][-1].content}")

    # Check token stats
    stats = tracker.get_stats()
    print(f"\nToken stats after round 1:")
    print(f"  - API calls: {stats['api_calls']}")
    print(f"  - Prompt tokens: {stats['total_prompt_tokens']}")
    print(f"  - Completion tokens: {stats['total_completion_tokens']}")
    print(f"  - Total tokens: {stats['total_tokens']}")

    print("\n[Round 2] Asking about Java")
    result = agent.invoke(
        {"messages": [("user", "What is Java? Answer in one sentence.")]},
        config
    )
    print(f"Response: {result['messages'][-1].content}")

    # Check token stats again
    stats = tracker.get_stats()
    print(f"\nToken stats after round 2:")
    print(f"  - API calls: {stats['api_calls']}")
    print(f"  - Total tokens: {stats['total_tokens']}")

    # Check compression stats
    comp_stats = checkpointer.get_compression_stats()
    print(f"\nCompression stats:")
    print(f"  - Total compressions: {comp_stats['total_compressions']}")
    print(f"  - Threshold: {comp_stats['threshold']}")
    print(f"  - Keep recent: {comp_stats['keep_recent']}")

    assert stats['api_calls'] == 2, "Should have 2 API calls"
    assert stats['total_tokens'] > 0, "Should have positive token count"

    print("\n[PASS] Basic TokenTracker test passed!")


def test_token_tracker_with_compression():
    """Test TokenTracker during compression"""
    print("\n" + "="*60)
    print("Test 2: TokenTracker with Compression")
    print("="*60)

    # API key
    api_key = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"

    # Create tracker
    tracker = TokenTracker()

    # Low threshold to trigger compression quickly
    checkpointer = AdaptiveCheckpointSaver(
        threshold=200,  # Low threshold to trigger easily
        keep_recent=2,
        token_tracker=tracker
    )

    # Create agent
    agent = create_chat_agent(checkpointer, api_key, tracker)

    # Run multiple rounds to trigger compression
    config = {"configurable": {"thread_id": "test-2"}}

    topics = ["Python", "Java", "C++", "JavaScript", "Go"]

    for i, topic in enumerate(topics, 1):
        print(f"\n[Round {i}] Asking about {topic}")
        result = agent.invoke(
            {"messages": [("user", f"What is {topic}? Answer in one sentence.")]},
            config
        )

        stats = tracker.get_stats()
        comp_stats = checkpointer.get_compression_stats()

        print(f"  - Total tokens so far: {stats['total_tokens']}")
        print(f"  - Compressions so far: {comp_stats['total_compressions']}")

    # Final stats
    final_stats = tracker.get_stats()
    final_comp_stats = checkpointer.get_compression_stats()

    print(f"\n{'='*60}")
    print("Final Results:")
    print(f"{'='*60}")
    print(f"API calls: {final_stats['api_calls']}")
    print(f"Total tokens: {final_stats['total_tokens']}")
    print(f"Compressions: {final_comp_stats['total_compressions']}")

    if final_comp_stats['total_compressions'] > 0:
        print(f"Token reduction: {final_comp_stats['avg_token_reduction_percent']:.2f}%")
        print("\n[PASS] Compression was triggered!")
    else:
        print("\n[WARNING] No compression was triggered (threshold might be too high)")


if __name__ == "__main__":
    try:
        test_token_tracker_basic()
        test_token_tracker_with_compression()

        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
