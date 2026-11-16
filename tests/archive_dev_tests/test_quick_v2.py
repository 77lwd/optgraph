"""
Quick test: 10 rounds to verify Memory v2.0 works
"""

import sys
sys.path.insert(0, '.')

from scenario_utils_v2 import run_scenario_test_v2, save_results_v2


def scenario_quick_test(agent, config):
    """Quick 10-round test"""

    # Round 1
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing.")]},
        config
    )

    # Rounds 2-10
    for i in range(2, 11):
        agent.invoke(
            {"messages": [("user", f"Question {i}.")]},
            config
        )

    # Final recall (use explicit recall keyword)
    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name?")]},
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

    print("Quick Test: Memory v2.0 (10 rounds)")
    print("="*70)

    results = run_scenario_test_v2(
        scenario_name="Quick Test (10 rounds)",
        scenario_func=scenario_quick_test,
        llm_config=llm_config,
        expected_rounds=11
    )

    save_results_v2(results, "test_results/quick_test_v2.json")

    print(f"\nToken change: {results['comparison']['token_change_percent']:+.1f}%")
