"""
Fast test: only 10 rounds to quickly check if agent can recall from summary
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
    print("Fast Recall Test (10 rounds)")
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

    # Create checkpointer with reasonable threshold
    tracker = TokenTracker()
    checkpointer = AdaptiveCheckpointSaver(
        threshold=2000,  # Reasonable threshold
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

    thread_id = "fast-test-{}".format(int(time.time()*1000))
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: Provide info
    print("\n[Round 1] User provides information...")
    agent.invoke(
        {"messages": [("user", "My name is Alice, I live in Beijing, I love Python.")]},
        config
    )

    # Rounds 2-40: Filler with longer messages (trigger compression)
    print("\n[Rounds 2-40] Filler...")
    for i in range(2, 41):
        agent.invoke(
            {"messages": [("user", "Tell me an interesting fact about topic number {}. Please be detailed and thorough.".format(i))]},
            config
        )
        if i % 10 == 0:
            comp_stats = checkpointer.get_compression_stats()
            print("  [Round {}] Compressions: {}".format(i, comp_stats['total_compressions']))

    # Round 41: Test recall
    print("\n[Round 41] Testing recall...")
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content
    print("\nAgent's response:")
    print(response)
    print("\n" + "="*70)

    # Check results
    response_lower = response.lower()
    has_alice = 'alice' in response_lower
    has_beijing = 'beijing' in response_lower
    has_python = 'python' in response_lower

    print("Quality Check:")
    print("  Contains 'Alice': {}".format(has_alice))
    print("  Contains 'Beijing': {}".format(has_beijing))
    print("  Contains 'Python': {}".format(has_python))
    print("  Quality: {:.1f}%".format((has_alice + has_beijing + has_python) / 3.0 * 100))

    comp_stats = checkpointer.get_compression_stats()
    print("\nCompression Stats:")
    print("  Total compressions: {}".format(comp_stats['total_compressions']))
    print("  Summary calls: {}".format(comp_stats['total_summary_calls']))

    print("="*70)


if __name__ == "__main__":
    main()
