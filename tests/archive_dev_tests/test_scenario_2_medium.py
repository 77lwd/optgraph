"""
Scenario 2: Medium Conversation (30 rounds)

Purpose: Standard baseline scenario
Expected: ~30-40% token savings (known: 34.4%)
Time: ~5-8 minutes
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import run_scenario_test, save_results


def scenario_medium_conversation(agent, config):
    """Medium conversation - baseline scenario"""

    # Round 1: Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-30: Standard questions
    for i in range(2, 31):
        agent.invoke(
            {"messages": [("user", f"Tell me about topic {i}.")]},
            config
        )

    # Final recall test
    result = agent.invoke(
        {"messages": [("user", "What is my name, city, and hobby?")]},
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

    print("Starting Scenario 2: Medium Conversation")
    print("This will take ~5-8 minutes\n")

    results = run_scenario_test(
        scenario_name="Medium Conversation (30 rounds)",
        scenario_func=scenario_medium_conversation,
        llm_config=llm_config,
        expected_rounds=30
    )

    # Save results
    save_results(results, "test_results/scenario_2_medium.json")

    print("[OK] Scenario 2 completed!")
    print(f"  Token reduction: {results['savings']['token_reduction_percent']:.1f}%")


if __name__ == "__main__":
    main()
