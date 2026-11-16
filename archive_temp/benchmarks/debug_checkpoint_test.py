"""
Debug test: Check what's actually in the checkpoint and what agent sees
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
    print("Debug Checkpoint Test")
    print("="*70)

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.7,
    )

    summarizer_llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,
    )

    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=500,  # Low to trigger fast
        keep_recent=3,
        summarizer_llm=summarizer_llm
    )

    def chat_node(state):
        print("\n[chat_node] Received messages:")
        for i, msg in enumerate(state["messages"]):
            print("  [{}] {}: {}".format(i+1, msg.type, str(msg.content)[:80]))

        response = llm.invoke(state["messages"])
        tracker.record_usage(response)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.set_finish_point("chat")

    agent = graph.compile(checkpointer=checkpointer)

    thread_id = "debug-test-{}".format(int(time.time()*1000))
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1
    print("\n=== Round 1 ===")
    agent.invoke(
        {"messages": [("user", "My name is Alice, I live in Beijing, I love Python.")]},
        config
    )

    # Round 2-8: Trigger compression
    for i in range(2, 9):
        print("\n=== Round {} ===".format(i))
        agent.invoke(
            {"messages": [("user", "Tell me something interesting.")]},
            config
        )

    # Check what's in checkpoint
    print("\n" + "="*70)
    print("Checking checkpoint content...")
    print("="*70)

    checkpoint = checkpointer.get(config)
    if checkpoint:
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        print("Total messages in checkpoint: {}".format(len(messages)))
        for i, msg in enumerate(messages):
            print("\n[Message {}] Type: {}".format(i+1, msg.type))
            print("Content: {}".format(str(msg.content)[:200]))

    # Round 9: Test recall
    print("\n" + "="*70)
    print("=== Round 9: Test Recall ===")
    print("="*70)
    result = agent.invoke(
        {"messages": [("user", "What is my name?")]},
        config
    )

    response = result['messages'][-1].content
    print("\nAgent's response:")
    print(response)
    print("\n" + "="*70)
    print("Contains 'Alice': {}".format('alice' in response.lower()))
    print("="*70)


if __name__ == "__main__":
    main()
