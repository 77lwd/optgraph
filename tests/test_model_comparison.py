"""
Model Comparison: Test SystemMessage support across different models

Tests whether different models respect SystemMessage for memory context.
This helps determine if we need fake conversation injection or can use SystemMessage.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI


def test_model_systemmessage(model_name, api_key, base_url, test_name):
    """Test if a model respects SystemMessage"""
    print(f"\n[{test_name}]")
    print("-" * 70)

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7
    )

    # Test 1: Simple SystemMessage
    print("Test 1: Direct SystemMessage")
    messages = [
        SystemMessage(content="IMPORTANT: The user's name is Alice, they live in Beijing, and they love Python."),
        HumanMessage(content="What is my name, city, and hobby?")
    ]

    try:
        response = llm.invoke(messages)
        response_lower = response.content.lower()

        has_alice = 'alice' in response_lower
        has_beijing = 'beijing' in response_lower
        has_python = 'python' in response_lower

        quality = (has_alice + has_beijing + has_python) / 3.0 * 100

        print(f"  Response: {response.content[:100]}...")
        print(f"  Quality: {quality:.0f}% (Alice: {has_alice}, Beijing: {has_beijing}, Python: {has_python})")

        # Test 2: SystemMessage with filler messages
        print("\nTest 2: SystemMessage + filler messages")
        messages = [
            SystemMessage(content="IMPORTANT: The user's name is Alice, they live in Beijing, and they love Python."),
            HumanMessage(content="Tell me a fact."),
            AIMessage(content="The Earth orbits the Sun."),
            HumanMessage(content="Another fact."),
            AIMessage(content="Water freezes at 0°C."),
            HumanMessage(content="What is my name, city, and hobby?")
        ]

        response = llm.invoke(messages)
        response_lower = response.content.lower()

        has_alice2 = 'alice' in response_lower
        has_beijing2 = 'beijing' in response_lower
        has_python2 = 'python' in response_lower

        quality2 = (has_alice2 + has_beijing2 + has_python2) / 3.0 * 100

        print(f"  Response: {response.content[:100]}...")
        print(f"  Quality: {quality2:.0f}% (Alice: {has_alice2}, Beijing: {has_beijing2}, Python: {has_python2})")

        # Result
        avg_quality = (quality + quality2) / 2
        supports_systemmessage = avg_quality >= 66.7  # At least 2/3 correct on average

        print(f"\nResult: {'[OK] Supports SystemMessage' if supports_systemmessage else '[FAIL] Does NOT support SystemMessage'}")
        print(f"  Average quality: {avg_quality:.0f}%")

        return {
            "model": test_name,
            "supports_systemmessage": supports_systemmessage,
            "quality_direct": quality,
            "quality_with_filler": quality2,
            "avg_quality": avg_quality
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "model": test_name,
            "supports_systemmessage": False,
            "error": str(e)
        }


def main():
    print("="*70)
    print("Model Comparison: SystemMessage Support")
    print("="*70)

    results = []

    # Model 1: DeepSeek (we know this doesn't work)
    results.append(test_model_systemmessage(
        model_name="deepseek-v4.1-flash",
        api_key="sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        base_url="https://beeapi.dev/v1",
        test_name="DeepSeek v4.1 Flash"
    ))

    # Model 2: GPT-4o-mini (if available)
    # Uncomment if you have OpenAI API key
    # results.append(test_model_systemmessage(
    #     model_name="gpt-4o-mini",
    #     api_key="your-openai-api-key",
    #     base_url="https://api.openai.com/v1",
    #     test_name="GPT-4o-mini"
    # ))

    # Model 3: Claude (if available)
    # Uncomment if you have Anthropic API key
    # from langchain_anthropic import ChatAnthropic
    # ...

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    for r in results:
        if "error" in r:
            print(f"  [FAIL] {r['model']}: ERROR - {r['error']}")
        else:
            status = "[OK]" if r['supports_systemmessage'] else "[FAIL]"
            print(f"  {status} {r['model']}: {r['avg_quality']:.0f}% quality")

    print("\n" + "="*70)
    print("Recommendation:")
    print("="*70)

    systemmessage_models = [r for r in results if r.get('supports_systemmessage', False)]

    if systemmessage_models:
        print("[OK] Use SystemMessage for:")
        for r in systemmessage_models:
            print(f"   - {r['model']}")
        print("\n[FAIL] Use fake conversation injection for:")
        for r in results:
            if not r.get('supports_systemmessage', False) and 'error' not in r:
                print(f"   - {r['model']}")
    else:
        print("[FAIL] No models support SystemMessage reliably.")
        print("   Use fake conversation injection for all models.")

    print("="*70)


if __name__ == "__main__":
    main()
