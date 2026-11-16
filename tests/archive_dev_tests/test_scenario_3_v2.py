"""
Scenario 3 with Memory v2.0: Long Conversation (50 rounds)

Purpose: Test Memory v2.0 on the scenario that caused v1 to fail catastrophically
Expected: ~0-5% overhead (vs v1's -322% disaster)
"""

import sys
sys.path.insert(0, '.')

from scenario_utils_v2 import run_scenario_test_v2, save_results_v2


def scenario_long_conversation(agent, config):
    """Long conversation - 50 rounds"""

    # Round 1: Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming.")]},
        config
    )

    # Rounds 2-50: Continuous questions (no recall needed)
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

    print("="*70)
    print("Testing Memory v2.0 on Scenario 3 (The one that killed v1)")
    print("="*70)
    print("\nBackground:")
    print("  - Scenario 3 caused v1 to fail with -322% (56万 tokens overhead)")
    print("  - Root cause: Summary passed every round")
    print("  - v2 design: Memory in state, only injected on recall")
    print("\nExpected results:")
    print("  - Rounds 1-50: Zero overhead (no recall)")
    print("  - Round 51: Small overhead (1 recall)")
    print("  - Overall: 0-5% overhead vs baseline")
    print("="*70)
    print("\nStarting test (will take ~8-12 minutes)...\n")

    results = run_scenario_test_v2(
        scenario_name="Long Conversation (50 rounds) - Memory v2.0",
        scenario_func=scenario_long_conversation,
        llm_config=llm_config,
        expected_rounds=51
    )

    # Save results
    save_results_v2(results, "test_results/scenario_3_long_v2.json")

    # Final verdict
    print("\n" + "="*70)
    print("VERDICT")
    print("="*70)

    token_change = results['comparison']['token_change_percent']

    if abs(token_change) < 5:
        verdict = "SUCCESS"
        emoji = "✓"
        explanation = "Zero overhead achieved! v2 design works as expected."
    elif token_change < -5:
        verdict = "BETTER THAN EXPECTED"
        emoji = "✓✓"
        explanation = f"Achieved {abs(token_change):.1f}% savings! Even better than zero overhead."
    elif token_change < 20:
        verdict = "ACCEPTABLE"
        emoji = "~"
        explanation = f"Small overhead ({token_change:.1f}%), but much better than v1's -322%."
    else:
        verdict = "NEEDS INVESTIGATION"
        emoji = "✗"
        explanation = f"Overhead too high ({token_change:.1f}%). Expected ~0-5%."

    print(f"{emoji} {verdict}")
    print(f"  Token change: {token_change:+.1f}% vs baseline")
    print(f"  {explanation}")
    print()

    # Comparison with v1
    print("Comparison with v1:")
    print(f"  v1 result: -322% (catastrophic failure)")
    print(f"  v2 result: {token_change:+.1f}%")
    print(f"  Improvement: {-322 - token_change:.1f} percentage points!")

    print("="*70)


if __name__ == "__main__":
    main()
