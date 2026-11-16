"""
Quick test: Scenario 1 with optimized v2 (skip compression for short conversations)
"""

import sys
sys.path.insert(0, '.')

import time
from langchain_openai import ChatOpenAI
from scenario_utils_v2 import create_baseline_agent, create_memory_v2_agent


def scenario_1_short(agent, config):
    """Scenario 1: Short conversation (10 rounds)"""
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    for i in range(2, 10):
        agent.invoke(
            {"messages": [("user", f"Tell me about topic {i}.")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name and city?")]},
        config
    )
    return result


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Scenario 1 - Optimized Memory v2.0")
    print("="*70)
    print("Optimization: min_total_messages=15 (skip compression for <15 messages)")
    print()

    # Baseline
    print("[1/2] Running BASELINE...")
    baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
    baseline_config = {"configurable": {"thread_id": f"baseline-opt-{int(time.time()*1000)}"}}

    try:
        baseline_result = scenario_1_short(baseline_agent, baseline_config)
        baseline_stats = baseline_tracker.get_stats()
        print(f"  [OK] Baseline: {baseline_stats['total_tokens']:,} tokens")
    except Exception as e:
        print(f"  [ERROR] Baseline failed: {e}")
        return

    # Memory v2 optimized
    print("[2/2] Running MEMORY V2 (Optimized)...")
    memory_agent, memory_tracker = create_memory_v2_agent(llm_config, max_messages=20, keep_recent=10)
    memory_config = {"configurable": {"thread_id": f"memory-opt-{int(time.time()*1000)}"}}

    try:
        memory_result = scenario_1_short(memory_agent, memory_config)
        memory_stats = memory_tracker.get_stats()
        print(f"  [OK] Memory v2: {memory_stats['total_tokens']:,} tokens")
    except Exception as e:
        print(f"  [ERROR] Memory v2 failed: {e}")
        return

    # Calculate
    token_diff = memory_stats['total_tokens'] - baseline_stats['total_tokens']
    token_change = (token_diff / baseline_stats['total_tokens']) * 100

    # Quality check
    baseline_response = baseline_result['messages'][-1].content.lower()
    memory_response = memory_result['messages'][-1].content.lower()

    baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response)) / 2.0 * 100
    memory_quality = (('alice' in memory_response) + ('beijing' in memory_response)) / 2.0 * 100

    # Results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"Baseline:  {baseline_stats['total_tokens']:,} tokens, Quality: {baseline_quality:.0f}%")
    print(f"Memory v2: {memory_stats['total_tokens']:,} tokens, Quality: {memory_quality:.0f}%")
    print(f"Change:    {token_diff:+,} tokens ({token_change:+.1f}%)")
    print()
    print("Comparison:")
    print(f"  v2 (before optimization): +31.4% overhead")
    print(f"  v2 (after optimization):  {token_change:+.1f}%")
    print()

    if abs(token_change) < 5:
        print("Result: SUCCESS - Near zero overhead!")
    elif token_change < -10:
        print("Result: BETTER THAN EXPECTED - Savings achieved!")
    elif token_change > 20:
        print("Result: STILL HAS OVERHEAD - Need further investigation")
    else:
        print("Result: ACCEPTABLE - Small overhead within range")

    print("="*70)


if __name__ == "__main__":
    main()
