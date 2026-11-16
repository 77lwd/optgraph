"""
Test Scenario 1 with optimized Memory v2.0 (dynamic compression threshold)
"""

import sys
sys.path.insert(0, '.')

from scenario_utils_v2 import run_scenario_test_v2, save_results_v2


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


if __name__ == "__main__":
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("Testing Scenario 1 with OPTIMIZED Memory v2.0")
    print("="*70)
    print("Optimization: Skip compression for conversations < 15 messages")
    print("="*70)
    print()

    results = run_scenario_test_v2(
        scenario_name="Scenario 1: Short (10 rounds) - Optimized",
        scenario_func=scenario_1_short,
        llm_config=llm_config,
        expected_rounds=10
    )

    save_results_v2(results, "test_results/scenario_1_short_v2_optimized.json")

    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)
    print(f"v2 (original):  +31.4% overhead (compression triggered)")
    print(f"v2 (optimized): {results['comparison']['token_change_percent']:+.1f}% (compression skipped)")
    print("="*70)
