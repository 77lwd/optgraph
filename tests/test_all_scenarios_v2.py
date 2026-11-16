"""
Batch test: Run all scenarios with Memory v2.0

Scenarios:
1. Short (10 rounds)
2. Medium (30 rounds)
3. Long (50 rounds) - already done
4. Long Messages (20 rounds)
5. Realistic Mixed (25 rounds)
"""

import sys
sys.path.insert(0, '.')

from scenario_utils_v2 import run_scenario_test_v2, save_results_v2


# === Scenario Definitions ===

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


def scenario_2_medium(agent, config):
    """Scenario 2: Medium conversation (30 rounds)"""
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]},
        config
    )

    for i in range(2, 30):
        agent.invoke(
            {"messages": [("user", f"Question {i}: Tell me something interesting.")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name, city, and hobby?")]},
        config
    )
    return result


def scenario_4_long_messages(agent, config):
    """Scenario 4: Long messages (20 rounds)"""
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python programming. I'm working on OptGraph project to optimize LangGraph's token usage.")]},
        config
    )

    for i in range(2, 20):
        agent.invoke(
            {"messages": [("user", f"Question {i}: Can you explain in detail about artificial intelligence, machine learning, and deep learning? Please provide comprehensive examples and use cases.")]},
            config
        )

    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name, city, and what project am I working on?")]},
        config
    )
    return result


def scenario_5_realistic(agent, config):
    """Scenario 5: Realistic mixed conversation (25 rounds)"""
    # Introduction
    agent.invoke(
        {"messages": [("user", "Hi! My name is Alice, I live in Beijing.")]},
        config
    )

    # Mixed questions (short and long)
    questions = [
        "What's the weather like?",
        "Tell me about Python programming in detail.",
        "Quick question: what's 2+2?",
        "Explain machine learning and its applications in modern technology.",
        "Do you like pizza?",
        "Can you describe the process of training a neural network?",
        "What time is it?",
        "Tell me everything about LangGraph and agent orchestration.",
        "Random question.",
        "Explain token optimization strategies in LLM applications.",
        "Another quick one.",
        "What are the best practices for building production AI systems?",
        "Short question.",
        "Describe memory management in conversational AI agents.",
        "Simple query.",
        "What are the trade-offs between different compression algorithms?",
        "Question 17.",
        "Explain the architecture of modern language models.",
        "Question 19.",
        "What are the challenges in scaling AI systems?",
        "Question 21.",
        "Describe retrieval-augmented generation techniques.",
        "Question 23.",
        "Final question.",
    ]

    for i, q in enumerate(questions, start=2):
        agent.invoke(
            {"messages": [("user", q)]},
            config
        )

    # Final recall
    result = agent.invoke(
        {"messages": [("user", "Remind me: what is my name and where do I live?")]},
        config
    )
    return result


# === Main Execution ===

def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    scenarios = [
        {
            "name": "Scenario 1: Short (10 rounds)",
            "func": scenario_1_short,
            "rounds": 10,
            "output": "test_results/scenario_1_short_v2.json"
        },
        {
            "name": "Scenario 2: Medium (30 rounds)",
            "func": scenario_2_medium,
            "rounds": 30,
            "output": "test_results/scenario_2_medium_v2.json"
        },
        {
            "name": "Scenario 4: Long Messages (20 rounds)",
            "func": scenario_4_long_messages,
            "rounds": 20,
            "output": "test_results/scenario_4_long_messages_v2.json"
        },
        {
            "name": "Scenario 5: Realistic Mixed (25 rounds)",
            "func": scenario_5_realistic,
            "rounds": 25,
            "output": "test_results/scenario_5_realistic_v2.json"
        }
    ]

    print("="*70)
    print("BATCH TEST: All Scenarios with Memory v2.0")
    print("="*70)
    print(f"Total scenarios: {len(scenarios)}")
    print("Note: Scenario 3 (50 rounds) already completed")
    print("="*70)
    print()

    all_results = []

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Running: {scenario['name']}")
        print("-"*70)

        try:
            results = run_scenario_test_v2(
                scenario_name=scenario['name'],
                scenario_func=scenario['func'],
                llm_config=llm_config,
                expected_rounds=scenario['rounds']
            )

            save_results_v2(results, scenario['output'])
            all_results.append(results)

            print(f"[OK] {scenario['name']} completed")
            print(f"     Token change: {results['comparison']['token_change_percent']:+.1f}%")
            print()

        except Exception as e:
            print(f"[ERROR] {scenario['name']} failed: {e}")
            print()

    # Summary
    print("\n" + "="*70)
    print("BATCH TEST SUMMARY")
    print("="*70)
    print(f"\n{'Scenario':<40} {'Token Change':>15} {'Quality':>10}")
    print("-"*70)

    for result in all_results:
        scenario_name = result['scenario']
        token_change = result['comparison']['token_change_percent']
        quality = result['quality']['memory_v2_percent']
        print(f"{scenario_name:<40} {token_change:>14.1f}% {quality:>9.0f}%")

    if all_results:
        avg_change = sum(r['comparison']['token_change_percent'] for r in all_results) / len(all_results)
        print("-"*70)
        print(f"{'Average':<40} {avg_change:>14.1f}%")

    print("="*70)
    print("\nAll tests completed!")


if __name__ == "__main__":
    main()
