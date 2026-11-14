"""
Edge Cases Test: Test robustness in unusual scenarios
"""

import time
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from optgraph.memory_state import (
    MemoryState,
    should_compress,
    compress_memory,
    get_context_with_memory
)


def create_agent(llm_config, max_messages=10, keep_recent=5):
    """Create chat agent"""
    main_llm = ChatOpenAI(**llm_config)

    summarizer_config = llm_config.copy()
    summarizer_config["temperature"] = 0.3
    summarizer_llm = ChatOpenAI(**summarizer_config)

    def chat_node(state: MemoryState):
        messages = get_context_with_memory(state)
        response = main_llm.invoke(messages)
        return {"messages": [response]}

    def compress_node(state: MemoryState):
        return compress_memory(state, summarizer_llm, keep_recent)

    def route_after_chat(state: MemoryState):
        return "compress" if should_compress(state, max_messages) else END

    builder = StateGraph(MemoryState)
    builder.add_node("chat", chat_node)
    builder.add_node("compress", compress_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", route_after_chat, {"compress": "compress", END: END})
    builder.add_edge("compress", END)

    return builder.compile(checkpointer=MemorySaver())


def test_no_introduction(llm_config):
    """Edge case 1: User never introduces themselves"""
    print("\n[Edge Case 1] No self-introduction")
    print("-" * 70)

    agent = create_agent(llm_config)
    thread_id = f"edge1-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Start without introduction
    agent.invoke({"messages": [("user", "What's the weather like?")]}, config)

    for i in range(2, 13):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    result = agent.invoke({"messages": [("user", "What is my name?")]}, config)

    response = result['messages'][-1].content.lower()
    correct = "don't know" in response or "haven't" in response or "didn't" in response

    print(f"  Response: {result['messages'][-1].content[:100]}...")
    print(f"  Correct behavior: {correct} (should say 'don't know')")

    return {"test": "no_introduction", "passed": correct}


def test_name_at_end(llm_config):
    """Edge case 2: Name appears at end of sentence"""
    print("\n[Edge Case 2] Name at end of sentence")
    print("-" * 70)

    agent = create_agent(llm_config)
    thread_id = f"edge2-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Name at end
    agent.invoke({"messages": [("user", "Hello! I'm Alice.")]}, config)

    for i in range(2, 13):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    result = agent.invoke({"messages": [("user", "What is my name?")]}, config)

    response = result['messages'][-1].content.lower()
    has_alice = 'alice' in response

    print(f"  Response: {result['messages'][-1].content[:100]}...")
    print(f"  Contains 'Alice': {has_alice}")

    return {"test": "name_at_end", "passed": has_alice}


def test_multiple_preferences(llm_config):
    """Edge case 3: Multiple preferences"""
    print("\n[Edge Case 3] Multiple preferences")
    print("-" * 70)

    agent = create_agent(llm_config)
    thread_id = f"edge3-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Multiple preferences
    agent.invoke({"messages": [("user", "Hi! I'm Bob. I love Python, Java, and JavaScript.")]}, config)

    for i in range(2, 13):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    result = agent.invoke({"messages": [("user", "What programming languages do I like?")]}, config)

    response = result['messages'][-1].content.lower()
    has_python = 'python' in response
    has_java = 'java' in response  # Will match both Java and JavaScript

    print(f"  Response: {result['messages'][-1].content[:150]}...")
    print(f"  Contains Python: {has_python}")
    print(f"  Contains Java*: {has_java}")

    return {"test": "multiple_preferences", "passed": has_python and has_java}


def test_info_update(llm_config):
    """Edge case 4: User updates their information"""
    print("\n[Edge Case 4] Information update")
    print("-" * 70)

    agent = create_agent(llm_config)
    thread_id = f"edge4-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Initial info
    agent.invoke({"messages": [("user", "Hi! I'm Alice from Beijing.")]}, config)

    for i in range(2, 8):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    # Update info
    agent.invoke({"messages": [("user", "By the way, I moved to Shanghai now.")]}, config)

    for i in range(9, 13):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    result = agent.invoke({"messages": [("user", "Where do I live?")]}, config)

    response = result['messages'][-1].content.lower()
    has_shanghai = 'shanghai' in response
    has_beijing = 'beijing' in response

    print(f"  Response: {result['messages'][-1].content[:100]}...")
    print(f"  Contains Shanghai: {has_shanghai}")
    print(f"  Contains Beijing (old): {has_beijing}")
    print(f"  Behavior: {'Updated ✓' if has_shanghai and not has_beijing else 'Partial/Mixed'}")

    # Pass if mentions Shanghai (even if also mentions Beijing as "old location")
    return {"test": "info_update", "passed": has_shanghai}


def test_very_long_introduction(llm_config):
    """Edge case 5: Very long self-introduction"""
    print("\n[Edge Case 5] Very long introduction")
    print("-" * 70)

    agent = create_agent(llm_config)
    thread_id = f"edge5-{int(time.time()*1000)}"
    config = {"configurable": {"thread_id": thread_id}}

    # Long intro
    long_intro = """Hi! My name is Alice, I live in Beijing, China.
I'm a software engineer with 5 years of experience.
I love Python programming, especially for data science and machine learning.
I also enjoy JavaScript and TypeScript for web development.
In my free time, I like reading sci-fi novels and hiking in the mountains.
I'm currently learning Rust and Go."""

    agent.invoke({"messages": [("user", long_intro)]}, config)

    for i in range(2, 13):
        agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, config)

    result = agent.invoke({"messages": [("user", "What is my name and where do I live?")]}, config)

    response = result['messages'][-1].content.lower()
    has_alice = 'alice' in response
    has_beijing = 'beijing' in response

    print(f"  Response: {result['messages'][-1].content[:150]}...")
    print(f"  Contains Alice: {has_alice}")
    print(f"  Contains Beijing: {has_beijing}")

    return {"test": "long_introduction", "passed": has_alice and has_beijing}


def main():
    llm_config = {
        "model": "deepseek-v4.1-flash",
        "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
        "base_url": "https://beeapi.dev/v1",
        "temperature": 0.7
    }

    print("="*70)
    print("Edge Cases Test")
    print("="*70)

    results = []

    try:
        results.append(test_no_introduction(llm_config))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"test": "no_introduction", "passed": False, "error": str(e)})

    try:
        results.append(test_name_at_end(llm_config))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"test": "name_at_end", "passed": False, "error": str(e)})

    try:
        results.append(test_multiple_preferences(llm_config))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"test": "multiple_preferences", "passed": False, "error": str(e)})

    try:
        results.append(test_info_update(llm_config))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"test": "info_update", "passed": False, "error": str(e)})

    try:
        results.append(test_very_long_introduction(llm_config))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"test": "long_introduction", "passed": False, "error": str(e)})

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    passed = sum(1 for r in results if r['passed'])
    total = len(results)

    print(f"Passed: {passed}/{total}")

    for r in results:
        status = "[OK] PASS" if r['passed'] else "[FAIL] FAIL"
        print(f"  {status}: {r['test']}")

    print("="*70)


if __name__ == "__main__":
    main()
