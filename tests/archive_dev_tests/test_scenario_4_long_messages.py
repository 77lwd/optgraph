"""
Scenario 4: Long Messages (20 rounds)

Purpose: Test compression with large messages (code/documents)
Expected: ~35-45% token savings (large message deletion is effective)
Time: ~6-10 minutes
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import run_scenario_test, save_results


def scenario_long_messages(agent, config):
    """Long message conversation - code/documents"""

    # Round 1: Long introduction
    long_intro = (
        "Hi! My name is Alice, I'm a software engineer with 5 years of experience. "
        "I live in Beijing, China. I love Python programming, especially for data science "
        "and machine learning. I also enjoy JavaScript, TypeScript, and Go. "
        "In my free time, I contribute to open source projects and write technical blogs. "
        "I'm currently working on a project involving LangGraph and LLM applications. "
        "I'm interested in memory management, context compression, and efficient AI systems."
    )
    agent.invoke({"messages": [("user", long_intro)]}, config)

    # Rounds 2-20: Long questions (simulating code reviews, document analysis)
    for i in range(2, 21):
        long_message = (
            f"Question {i}: Can you help me analyze this code snippet? "
            "Here's what I'm working on: " + "placeholder_code " * 50 +
            f"The main issue I'm facing in iteration {i} is about performance optimization. "
            "I've tried several approaches but none seem to work efficiently. "
            "What would you recommend based on your experience with similar problems?"
        )
        agent.invoke({"messages": [("user", long_message)]}, config)

    # Final recall
    result = agent.invoke(
        {"messages": [("user", "What do you know about me? My name, location, and skills?")]},
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

    print("Starting Scenario 4: Long Messages")
    print("This will take ~6-10 minutes\n")

    results = run_scenario_test(
        scenario_name="Long Messages (20 rounds)",
        scenario_func=scenario_long_messages,
        llm_config=llm_config,
        expected_rounds=20
    )

    # Save results
    save_results(results, "test_results/scenario_4_long_messages.json")

    print("[OK] Scenario 4 completed!")
    print(f"  Token reduction: {results['savings']['token_reduction_percent']:.1f}%")


if __name__ == "__main__":
    main()
