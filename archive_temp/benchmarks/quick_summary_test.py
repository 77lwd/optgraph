"""
Quick test to see what the summary contains
"""

import time
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.token_tracker import TokenTracker


API_KEY = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"
MODEL = "deepseek-v4.1-flash"
BASE_URL = "https://beeapi.dev/v1"


def main():
    print("Quick summary test")
    print("="*70)

    # Create LLM
    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.7,
    )

    # Create summarizer
    summarizer_llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,
    )

    # Create checkpointer with summarizer
    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=2000,
        keep_recent=5,
        summarizer_llm=summarizer_llm
    )

    def chat_node(state):
        response = llm.invoke(state["messages"])
        tracker.record_usage(response)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.set_finish_point("chat")

    agent = graph.compile(checkpointer=checkpointer)

    thread_id = "quick-test-{}".format(int(time.time()*1000))
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: Provide info
    print("\n[Round 1] User provides information...")
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-40: Filler
    print("\n[Rounds 2-40] Filler conversation to trigger compression...")
    for i in range(2, 41):
        agent.invoke(
            {"messages": [("user", "Tell me a fact about science.")]},
            config
        )
        if i % 10 == 0:
            comp_stats = checkpointer.get_compression_stats()
            print("  [Round {}] Compressions: {}".format(i, comp_stats['total_compressions']))

    # Check checkpoint to see what's in there
    print("\n[After Round 40] Checking stored messages...")
    checkpoint = checkpointer.get(config)
    if checkpoint:
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        print("  Total messages in checkpoint: {}".format(len(messages)))
        for i, msg in enumerate(messages[:3]):  # Print first 3
            print("  Message {}: [{}] {}".format(i+1, msg.type, str(msg.content)[:100]))

    # Round 50: Test recall
    print("\n[Round 50] Testing recall...")
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content
    print("\nAgent's response:")
    print(response)

    print("\n" + "="*70)
    print("Check:")
    print("  Contains 'Alice': {}".format('alice' in response.lower()))
    print("  Contains 'Beijing': {}".format('beijing' in response.lower()))
    print("  Contains 'Python': {}".format('python' in response.lower()))


if __name__ == "__main__":
    main()
