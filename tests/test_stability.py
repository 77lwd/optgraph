"""
Stability Test: Run multiple times to check consistency
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


def create_agent(llm_config, max_messages=10, keep_recent=5):
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
        return compress_memory(state, summarizer_llm, keep_recent)

    def route_after_chat(state: MemoryState):
        return "compress" if should_compress(state, max_messages) else END

    builder = StateGraph(MemoryState)
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", route_after_chat, {"compress": "compress", END: END})
    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver())


def run_test(run_id: int, llm_config: dict) -> dict:
    """Run one test"""
    agent = create_agent(llm_config, max_messages=10, keep_recent=5)

    thread_id = f"stability-test-{run_id}-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: Introduce
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-12: Filler
    for i in range(2, 13):
        agent.invoke(
            {"messages": [("user", f"Tell me a fact about topic {i}.")]},
            config
        )

    # Round 13: Test recall
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
        config
    )

    response = result['messages'][-1].content.lower()

    return {
        "run_id": run_id,
        "has_alice": 'alice' in response,
        "has_beijing": 'beijing' in response,
        "has_python": 'python' in response,
        "quality": (('alice' in response) + ('beijing' in response) + ('python' in response)) / 3.0 * 100,
        "response_preview": result['messages'][-1].content[:100]
    }


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Stability Test: 10 runs")
    print("="*70)

    results = []
    for i in range(1, 11):
        print(f"\n[Run {i}/10] Testing...")
        try:
            result = run_test(i, llm_config)
            results.append(result)
            print(f"  Quality: {result['quality']:.1f}% (Alice: {result['has_alice']}, Beijing: {result['has_beijing']}, Python: {result['has_python']})")
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({
                "run_id": i,
                "has_alice": False,
                "has_beijing": False,
                "has_python": False,
                "quality": 0.0,
                "error": str(e)
            })

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    successful_runs = [r for r in results if r['quality'] == 100.0]
    failed_runs = [r for r in results if r['quality'] < 100.0]

    print(f"Total runs: {len(results)}")
    print(f"Successful (100%): {len(successful_runs)}")
    print(f"Failed (<100%): {len(failed_runs)}")
    print(f"Success rate: {len(successful_runs) / len(results) * 100:.1f}%")

    if failed_runs:
        print("\nFailed runs:")
        for r in failed_runs:
            print(f"  Run {r['run_id']}: {r['quality']:.1f}% - {r.get('response_preview', r.get('error', 'Unknown'))[:80]}")

    avg_quality = sum(r['quality'] for r in results) / len(results)
    print(f"\nAverage quality: {avg_quality:.1f}%")

    print("="*70)


if __name__ == "__main__":
    main()
