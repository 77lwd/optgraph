"""
Scenario 5: Realistic Mixed Conversation (25 rounds)

Purpose: Simulate real-world usage with mixed short/long messages
Expected: ~30-40% token savings
Time: ~5-8 minutes
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import run_scenario_test, save_results


def scenario_realistic_conversation(agent, config):
    """Realistic mixed conversation - tech Q&A"""

    # Introduction
    agent.invoke(
        {"messages": [("user", "Hi! I'm Alice from Beijing. I'm working with Python and LangGraph.")]},
        config
    )

    # Mix of short and long messages (realistic pattern)
    realistic_questions = [
        "What's LangGraph?",
        "How do I create a state graph? Please explain in detail with the key concepts and best practices.",
        "Thanks!",
        "Now, can you show me an example? Here's my current code: " + "code_snippet " * 30,
        "I see. What about checkpointers?",
        "I'm getting an error: 'RemoveMessage not found'. Here's the full traceback: " + "error_trace " * 20,
        "That worked!",
        "Next question: how do I optimize memory usage in long conversations?",
        "Can you explain the difference between State layer and Checkpointer layer?",
        "Interesting. What about compression strategies?",
        "How does RemoveMessage work exactly?",
        "What if I want to keep some messages forever?",
        "Can I use this with OpenAI models?",
        "What about rate limiting?",
        "How do I handle errors gracefully?",
        "What's the best practice for testing?",
        "Should I use async or sync?",
        "How do I deploy this to production?",
        "What about monitoring and logging?",
        "Any performance tips?",
        "How do I debug issues?",
        "What's the memory overhead?",
        "Can I customize the summarization prompt?",
        "What about security concerns?",
    ]

    # Run questions
    for question in realistic_questions:
        agent.invoke({"messages": [("user", question)]}, config)

    # Final recall
    result = agent.invoke(
        {"messages": [("user", "Remind me, what's my name and where am I from?")]},
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

    print("Starting Scenario 5: Realistic Mixed Conversation")
    print("This will take ~5-8 minutes\n")

    results = run_scenario_test(
        scenario_name="Realistic Mixed Conversation (25 rounds)",
        scenario_func=scenario_realistic_conversation,
        llm_config=llm_config,
        expected_rounds=25
    )

    # Save results
    save_results(results, "test_results/scenario_5_realistic.json")

    print("[OK] Scenario 5 completed!")
    print(f"  Token reduction: {results['savings']['token_reduction_percent']:.1f}%")


if __name__ == "__main__":
    main()
