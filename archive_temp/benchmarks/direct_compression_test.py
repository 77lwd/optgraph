"""
Direct compression test - test the _compress method directly
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from optgraph.checkpointer import AdaptiveCheckpointSaver


API_KEY = "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07"
MODEL = "deepseek-v4.1-flash"
BASE_URL = "https://beeapi.dev/v1"


def main():
    print("Direct Compression Test")
    print("="*70)

    # Create summarizer
    summarizer_llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,
    )

    # Create checkpointer
    checkpointer = AdaptiveCheckpointSaver(
        threshold=2000,
        keep_recent=5,
        summarizer_llm=summarizer_llm
    )

    # Create fake conversation with info in message 1
    messages = []

    # Message 1: User provides info
    messages.append(HumanMessage(content="Hi! My name is Alice, I live in Beijing, and I love Python programming."))
    messages.append(AIMessage(content="Nice to meet you Alice! Beijing is a great city, and Python is an excellent programming language."))

    # Messages 2-40: Filler
    for i in range(2, 21):
        messages.append(HumanMessage(content="Tell me a fact about topic {}.".format(i)))
        messages.append(AIMessage(content="Here is an interesting fact about topic {}: it is very fascinating and has many applications.".format(i)))

    print("\nBefore compression:")
    print("  Total messages: {}".format(len(messages)))
    print("  First message: {}".format(messages[0].content))

    # Compress
    print("\nCompressing with keep_recent=5...")
    compressed = checkpointer._compress(messages)

    print("\nAfter compression:")
    print("  Total messages: {}".format(len(compressed)))
    print("\nCompressed messages:")
    for i, msg in enumerate(compressed):
        print("  [{}] {}: {}".format(i+1, msg.type, str(msg.content)[:150]))

    # Check if info is in summary
    if compressed and compressed[0].type == 'system':
        summary_content = compressed[0].content.lower()
        print("\n" + "="*70)
        print("Summary Quality Check:")
        print("  Contains 'alice': {}".format('alice' in summary_content))
        print("  Contains 'beijing': {}".format('beijing' in summary_content))
        print("  Contains 'python': {}".format('python' in summary_content))
        print("="*70)
    else:
        print("\nERROR: No summary message found!")


if __name__ == "__main__":
    main()
