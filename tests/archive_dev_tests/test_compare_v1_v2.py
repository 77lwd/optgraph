"""
Quick comparison test: Memory v1 vs v2

Test scenario: 25 rounds with 1 recall
- v1: Passes summary every round (cumulative overhead)
- v2: Only passes memory when recall is triggered (zero baseline overhead)
"""

import sys
sys.path.insert(0, '.')

import time
from langchain_openai import ChatOpenAI

# Import v1 (old system)
from examples.chat_with_memory import create_chat_agent_with_memory

# Import v2 (new system)
from examples.chat_with_memory_v2 import create_chat_agent_v2


def estimate_tokens(text):
    """Rough token estimation"""
    return len(text) // 4


def run_test(agent, name, config):
    """Run test scenario and count tokens"""

    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")

    total_input_chars = 0
    total_output_chars = 0

    # Round 1: Introduction
    print(f"[Round 1] Introduction...")
    result = agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    # Estimate tokens for round 1
    input_text = "Hi! My name is Alice, I live in Beijing, and I love Python."
    output_text = result['messages'][-1].content

    total_input_chars += len(input_text)
    total_output_chars += len(output_text)

    # Rounds 2-20: Regular questions (no recall)
    print(f"[Rounds 2-20] Regular questions (should be zero overhead for v2)...")
    for i in range(2, 21):
        if i % 5 == 0:
            print(f"  Round {i}...")

        result = agent.invoke(
            {"messages": [("user", f"Question {i}: Tell me something.")]},
            config
        )

        input_text = f"Question {i}: Tell me something."
        output_text = result['messages'][-1].content

        total_input_chars += len(input_text)
        total_output_chars += len(output_text)

    # Round 21: Recall test
    print(f"[Round 21] Recall test...")
    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name and city?")]},
        config
    )

    input_text = "Remind me: what is my name and city?"
    output_text = result['messages'][-1].content

    total_input_chars += len(input_text)
    total_output_chars += len(output_text)

    # Check recall quality
    response_lower = output_text.lower()
    has_alice = 'alice' in response_lower
    has_beijing = 'beijing' in response_lower
    recall_quality = (has_alice + has_beijing) / 2.0 * 100

    print(f"\nRecall quality: {recall_quality:.0f}%")
    print(f"  - Has 'Alice': {has_alice}")
    print(f"  - Has 'Beijing': {has_beijing}")

    # Rounds 22-25: More regular questions
    print(f"[Rounds 22-25] More questions...")
    for i in range(22, 26):
        result = agent.invoke(
            {"messages": [("user", f"Question {i}.")]},
            config
        )

        input_text = f"Question {i}."
        output_text = result['messages'][-1].content

        total_input_chars += len(input_text)
        total_output_chars += len(output_text)

    # Estimate total tokens
    total_input_tokens = estimate_tokens(str(total_input_chars))
    total_output_tokens = estimate_tokens(str(total_output_chars))
    total_tokens = total_input_tokens + total_output_tokens

    print(f"\n{'-'*70}")
    print(f"Results for {name}:")
    print(f"  Total input chars: {total_input_chars:,}")
    print(f"  Total output chars: {total_output_chars:,}")
    print(f"  Estimated total tokens: ~{total_tokens:,}")
    print(f"  Recall quality: {recall_quality:.0f}%")
    print(f"{'-'*70}")

    return {
        "name": name,
        "input_chars": total_input_chars,
        "output_chars": total_output_chars,
        "total_tokens": total_tokens,
        "recall_quality": recall_quality
    }


def main():
    """Run comparison test"""

    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Memory System Comparison: v1 vs v2")
    print("="*70)
    print("\nTest scenario:")
    print("  - 25 rounds of conversation")
    print("  - 1 recall request (round 21)")
    print("  - Compare token usage and recall quality")
    print("\nExpected:")
    print("  - v1: High overhead (summary passed every round)")
    print("  - v2: Low overhead (memory only injected on recall)")
    print("="*70)

    results = []

    # Test v2 (new system) first
    print("\n\n[1/2] Testing Memory v2.0...")
    agent_v2 = create_chat_agent_v2(
        llm_config=llm_config,
        max_messages=20,
        keep_recent=10
    )
    thread_id_v2 = f"compare-v2-{int(time.time()*1000)}"
    config_v2 = {"configurable": {"thread_id": thread_id_v2}}

    result_v2 = run_test(agent_v2, "Memory v2.0", config_v2)
    results.append(result_v2)

    time.sleep(2)  # Brief pause

    # Test v1 (old system)
    print("\n\n[2/2] Testing Memory v1.0...")
    agent_v1 = create_chat_agent_with_memory(
        llm_config=llm_config,
        max_messages=20,
        keep_recent=10
    )
    thread_id_v1 = f"compare-v1-{int(time.time()*1000)}"
    config_v1 = {"configurable": {"thread_id": thread_id_v1}}

    result_v1 = run_test(agent_v1, "Memory v1.0", config_v1)
    results.append(result_v1)

    # Comparison
    print("\n\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)

    print("\n{:<15} {:>20} {:>20}".format("Metric", "Memory v1.0", "Memory v2.0"))
    print("-"*70)

    print("{:<15} {:>20,} {:>20,}".format(
        "Input chars",
        result_v1["input_chars"],
        result_v2["input_chars"]
    ))

    print("{:<15} {:>20,} {:>20,}".format(
        "Output chars",
        result_v1["output_chars"],
        result_v2["output_chars"]
    ))

    print("{:<15} {:>20,} {:>20,}".format(
        "Est. tokens",
        result_v1["total_tokens"],
        result_v2["total_tokens"]
    ))

    print("{:<15} {:>19.0f}% {:>19.0f}%".format(
        "Recall quality",
        result_v1["recall_quality"],
        result_v2["recall_quality"]
    ))

    # Calculate savings
    if result_v1["total_tokens"] > 0:
        token_diff = result_v2["total_tokens"] - result_v1["total_tokens"]
        savings_pct = (token_diff / result_v1["total_tokens"]) * 100

        print("\n" + "-"*70)
        print(f"Token difference: {token_diff:+,} ({savings_pct:+.1f}%)")

        if savings_pct < 0:
            print(f"Memory v2.0 saves {abs(savings_pct):.1f}% tokens!")
        elif savings_pct > 0:
            print(f"Memory v2.0 uses {savings_pct:.1f}% MORE tokens")
        else:
            print(f"Same token usage")

    print("="*70)

    # Analysis
    print("\nAnalysis:")
    print("  In this 25-round test:")
    print("  - Memory v1: Passes summary every round after compression")
    print("  - Memory v2: Only injects memory on round 21 (recall)")
    print("  - Expected: v2 should have lower/similar token usage")
    print("\nNote: This is a quick test. Full validation needs:")
    print("  - 50-100 round tests")
    print("  - Multiple recall scenarios")
    print("  - Comparison with baseline (no memory system)")
    print("="*70)


if __name__ == "__main__":
    main()
