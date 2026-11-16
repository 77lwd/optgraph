"""
Debug: Test if LLM respects SystemMessage
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek-v4.1-flash",
    api_key="sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
    base_url="https://beeapi.dev/v1",
    temperature=0.7
)

# Test 1: Direct question with SystemMessage
print("="*70)
print("Test 1: SystemMessage with context")
print("="*70)

messages = [
    SystemMessage(content="IMPORTANT: You already know the following about this user from earlier in the conversation:\n- Their name is Alice\n- They live in Beijing\n- They love/prefer: Python"),
    HumanMessage(content="What is my name, city, and hobby?")
]

response = llm.invoke(messages)
print(f"Response: {response.content}")
print(f"\nContains Alice: {'alice' in response.content.lower()}")
print(f"Contains Beijing: {'beijing' in response.content.lower()}")
print(f"Contains Python: {'python' in response.content.lower()}")

# Test 2: With filler messages in between
print("\n" + "="*70)
print("Test 2: SystemMessage + filler + question")
print("="*70)

messages = [
    SystemMessage(content="IMPORTANT: You already know the following about this user from earlier in the conversation:\n- Their name is Alice\n- They live in Beijing\n- They love/prefer: Python"),
    HumanMessage(content="Tell me a fact."),
    SystemMessage(content="Python uses indentation."),
    HumanMessage(content="Another fact."),
    SystemMessage(content="Beijing is the capital of China."),
    HumanMessage(content="What is my name, city, and hobby?")
]

response = llm.invoke(messages)
print(f"Response: {response.content}")
print(f"\nContains Alice: {'alice' in response.content.lower()}")
print(f"Contains Beijing: {'beijing' in response.content.lower()}")
print(f"Contains Python: {'python' in response.content.lower()}")
