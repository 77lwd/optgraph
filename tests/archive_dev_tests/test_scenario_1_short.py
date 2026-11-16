"""
Scenario 1: Short Conversation (10 rounds)

Purpose: Test if compression is triggered in short conversations
Expected: Little to no compression, savings ~0-10%
Time: ~3-5 minutes
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import run_scenario_test, save_results


def scenario_short_conversation(agent, config):
    """Short conversation - may not trigger compression"""

    # Round 1: Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    # Rounds 2-9: Quick questions
    for i in range(2, 10):
        agent.invoke(
            {"messages": [("user", f"Quick question {i}: What's the weather like?")]},
            config
        )

    # Round 10: Recall test
    result = agent.invoke(
        {"messages": [("user", "What is my name and city?")]},
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

    print("Starting Scenario 1: Short Conversation")
    print("This will take ~3-5 minutes\n")

    results = run_scenario_test(
        scenario_name="Short Conversation (10 rounds)",
        scenario_func=scenario_short_conversation,
        llm_config=llm_config,
        expected_rounds=10
    )

    # Save results
    save_results(results, "test_results/scenario_1_short.json")

    print("[OK] Scenario 1 completed!")
    print(f"  Token reduction: {results['savings']['token_reduction_percent']:.1f}%")


if __name__ == "__main__":
    main()
