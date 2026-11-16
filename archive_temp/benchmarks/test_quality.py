"""
Quality Test: Memory Retention with Compression

Tests whether the agent can remember early conversation information
after compression is triggered.

Test design:
- Round 1: User provides name, city, hobby
- Round 2-45: Filler conversation (triggers compression)
- Round 50: Test recall of the 3 pieces of information

Quality score = (remembered items / 3) * 100%
"""

import time
from datetime import datetime
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver
from optgraph.token_tracker import TokenTracker


# Configuration
API_KEY = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"
MODEL = "deepseek-v4.1-flash"
BASE_URL = "https://beeapi.dev/v1"


def create_chat_agent(checkpointer, tracker):
    """Create a chat agent with compression and token tracking"""

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.7,
    )

    def chat_node(state):
        """Chat node that calls LLM and tracks tokens"""
        response = llm.invoke(state["messages"])
        tracker.record_usage(response)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.set_finish_point("chat")

    return graph.compile(checkpointer=checkpointer)


def test_memory_retention_single(threshold, keep_recent, run_id):
    """Single memory retention test

    Args:
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep
        run_id: Test run identifier

    Returns:
        Dict with quality score and stats
    """
    print("\n[Run {}] threshold={}, keep_recent={}".format(run_id, threshold, keep_recent))

    # Create tracker and checkpointer WITH summarizer LLM
    tracker = TokenTracker()

    # Create summarizer LLM (same model, lower temperature for consistency)
    summarizer_llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,  # Lower temperature for more consistent summaries
    )

    checkpointer = AdaptiveCheckpointSaver(
        threshold=threshold,
        keep_recent=keep_recent,
        summarizer_llm=summarizer_llm
    )

    # Create agent
    agent = create_chat_agent(checkpointer, tracker)

    # Unique thread_id
    thread_id = "quality-test-{}-{}".format(keep_recent, int(time.time()*1000))
    config = {"configurable": {"thread_id": thread_id}}

    # Round 1: Provide information to remember
    print("  [Round 1] Providing information...")
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-45: Filler conversation to trigger compression
    topics = [
        "weather", "food", "music", "movies", "sports", "books", "travel",
        "technology", "art", "history", "science", "games", "pets", "nature",
        "health", "fashion", "cars", "photography", "cooking", "fitness",
        "architecture", "literature", "economics", "psychology", "astronomy",
        "biology", "chemistry", "physics", "mathematics", "philosophy",
        "politics", "geography", "languages", "dance", "theater",
        "sculpture", "painting", "poetry", "journalism", "education",
        "medicine", "engineering", "business", "marketing"
    ]

    for i in range(2, 46):
        topic = topics[i % len(topics)]
        agent.invoke(
            {"messages": [("user", "Tell me one interesting fact about {}.".format(topic))]},
            config
        )

        # Print compression status every 10 rounds
        if i % 10 == 0:
            comp_stats = checkpointer.get_compression_stats()
            print("  [Round {}] Compressions so far: {}".format(i, comp_stats['total_compressions']))

    # Rounds 46-49: More filler
    for i in range(46, 50):
        agent.invoke(
            {"messages": [("user", "What do you think about that?")]},
            config
        )

    # Round 50: Test recall
    print("  [Round 50] Testing recall...")
    result = agent.invoke(
        {"messages": [("user", "Can you remind me: what is my name, where do I live, and what do I love?")]},
        config
    )

    # Check what the agent remembers
    response = result['messages'][-1].content.lower()

    remembers_name = 'alice' in response
    remembers_city = 'beijing' in response
    remembers_hobby = 'python' in response

    quality_score = (int(remembers_name) + int(remembers_city) + int(remembers_hobby)) / 3.0

    # Get stats
    comp_stats = checkpointer.get_compression_stats()
    token_stats = tracker.get_stats()

    print("  Results:")
    print("    Name (Alice): {}".format("YES" if remembers_name else "NO"))
    print("    City (Beijing): {}".format("YES" if remembers_city else "NO"))
    print("    Hobby (Python): {}".format("YES" if remembers_hobby else "NO"))
    print("    Quality: {:.1f}%".format(quality_score * 100))
    print("    Compressions: {}".format(comp_stats['total_compressions']))
    print("    Total tokens: {}".format(token_stats['total_tokens']))

    return {
        "run_id": run_id,
        "threshold": threshold,
        "keep_recent": keep_recent,
        "remembers_name": remembers_name,
        "remembers_city": remembers_city,
        "remembers_hobby": remembers_hobby,
        "quality_score": quality_score,
        "compressions": comp_stats['total_compressions'],
        "total_tokens": token_stats['total_tokens'],
        "response_sample": response[:200]  # First 200 chars for debugging
    }


def test_memory_retention_avg(threshold, keep_recent, repetitions=3):
    """Run multiple memory retention tests and average results

    Args:
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep
        repetitions: Number of times to repeat the test

    Returns:
        Dict with averaged results
    """
    print("\n" + "="*70)
    print("Testing keep_recent={} (threshold={}, {} repetitions)".format(
        keep_recent, threshold, repetitions))
    print("="*70)

    results = []

    for i in range(1, repetitions + 1):
        result = test_memory_retention_single(threshold, keep_recent, i)
        results.append(result)

        # Wait a bit between runs
        if i < repetitions:
            time.sleep(2)

    # Calculate averages
    avg_quality = sum(r['quality_score'] for r in results) / len(results)
    avg_compressions = sum(r['compressions'] for r in results) / len(results)

    # Count how many times each item was remembered
    name_count = sum(1 for r in results if r['remembers_name'])
    city_count = sum(1 for r in results if r['remembers_city'])
    hobby_count = sum(1 for r in results if r['remembers_hobby'])

    print("\n" + "-"*70)
    print("AVERAGE RESULTS (keep_recent={})".format(keep_recent))
    print("-"*70)
    print("  Name remembered: {}/{} times".format(name_count, repetitions))
    print("  City remembered: {}/{} times".format(city_count, repetitions))
    print("  Hobby remembered: {}/{} times".format(hobby_count, repetitions))
    print("  Average quality: {:.1f}%".format(avg_quality * 100))
    print("  Average compressions: {:.1f}".format(avg_compressions))

    return {
        "keep_recent": keep_recent,
        "threshold": threshold,
        "repetitions": repetitions,
        "avg_quality_score": avg_quality,
        "avg_compressions": avg_compressions,
        "name_remembered_count": name_count,
        "city_remembered_count": city_count,
        "hobby_remembered_count": hobby_count,
        "individual_results": results
    }


def main():
    """Run complete quality test"""
    print("\n" + "="*70)
    print("OptGraph Phase 3: Quality Test (Memory Retention)")
    print("="*70)
    print("Start time: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print("\nTest design:")
    print("  - Round 1: User provides name (Alice), city (Beijing), hobby (Python)")
    print("  - Round 2-49: Filler conversation (triggers compression)")
    print("  - Round 50: Test recall of the 3 information items")
    print("  - Quality = (remembered items / 3) * 100%")
    print("  - Target: >= 90% quality")

    # Fixed threshold (proven optimal from efficiency test)
    threshold = 2000

    # Test different keep_recent values
    keep_recent_values = [5, 10, 15, 20]

    all_results = []

    for keep_recent in keep_recent_values:
        result = test_memory_retention_avg(
            threshold=threshold,
            keep_recent=keep_recent,
            repetitions=3
        )
        all_results.append(result)

    # Find minimum keep_recent with >= 90% quality
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)

    for result in all_results:
        quality_pct = result['avg_quality_score'] * 100
        status = "PASS" if quality_pct >= 90 else "FAIL"
        print("keep_recent={:2d}: {:.1f}% quality [{}]".format(
            result['keep_recent'], quality_pct, status))

    # Find optimal
    passing_results = [r for r in all_results if r['avg_quality_score'] >= 0.9]

    if passing_results:
        optimal = min(passing_results, key=lambda x: x['keep_recent'])
        print("\n" + "="*70)
        print("RECOMMENDATION")
        print("="*70)
        print("Optimal keep_recent: {}".format(optimal['keep_recent']))
        print("Quality: {:.1f}%".format(optimal['avg_quality_score'] * 100))
        print("Average compressions: {:.1f}".format(optimal['avg_compressions']))
        print("\nCombined with efficiency test results:")
        print("  Configuration: threshold=2000, keep_recent={}".format(optimal['keep_recent']))
        print("  Token savings: 41.4% (from previous efficiency test)")
    else:
        print("\nWARNING: No configuration achieved >= 90% quality!")
        print("Consider increasing keep_recent beyond 20 or adjusting threshold.")

    # Save results
    import json
    output = {
        "timestamp": datetime.now().isoformat(),
        "threshold": threshold,
        "test_design": {
            "rounds": 50,
            "info_round": 1,
            "test_round": 50,
            "repetitions_per_config": 3
        },
        "results": all_results
    }

    output_file = "benchmarks/quality_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to: {}".format(output_file))
    print("="*70)


if __name__ == "__main__":
    main()
