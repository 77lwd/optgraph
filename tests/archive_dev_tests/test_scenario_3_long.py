"""
Scenario 3: Long Conversation (50 rounds)

Purpose: Test scalability and cumulative compression effect
Expected: ~40-50% token savings
Time: ~8-12 minutes
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import run_scenario_test, save_results


def scenario_long_conversation(agent, config):
    """Long conversation - test scalability"""

    # Round 1: Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-50: Continuous questions
    for i in range(2, 51):
        agent.invoke(
            {"messages": [("user", f"Question {i}: Tell me something interesting.")]},
            config
        )

    # Final recall test
    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name, city, and hobby?")]},
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

    print("Starting Scenario 3: Long Conversation")
    print("This will take ~8-12 minutes\n")

    results = run_scenario_test(
        scenario_name="Long Conversation (50 rounds)",
        scenario_func=scenario_long_conversation,
        llm_config=llm_config,
        expected_rounds=50
    )

    # Save results
    save_results(results, "test_results/scenario_3_long.json")

    print("[OK] Scenario 3 completed!")
    print(f"  Token reduction: {results['savings']['token_reduction_percent']:.1f}%")


if __name__ == "__main__":
    main()
