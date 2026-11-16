"""
Simple compression test without external dependencies

Tests compression logic using simple mock objects.
Python 2.7 compatible.
"""


class MockMessage:
    """Simple mock message for testing"""
    def __init__(self, content, msg_type='user'):
        self.content = content
        self.type = msg_type


def count_tokens_simple(messages):
    """Simple token counting: 1 token = 4 chars"""
    total = 0
    for msg in messages:
        total += len(msg.content) // 4
    return total


def compress_messages(messages, keep_recent):
    """Simple compression: keep recent N messages

    This mimics the checkpointer's _compress logic
    """
    if len(messages) <= keep_recent:
        return messages

    # Keep only recent messages
    return messages[-keep_recent:]


def test_compression(message_count, threshold, keep_recent):
    """Test compression with given parameters"""
    print("\n[Test] messages={}, threshold={}, keep_recent={}".format(
        message_count, threshold, keep_recent))

    # Generate mock messages
    messages = []
    for i in range(message_count):
        # Simulate user/assistant pairs
        user_msg = MockMessage(
            "This is a user message number {} asking about something interesting. "
            "Please provide a detailed explanation with examples and best practices.".format(i),
            'user'
        )
        messages.append(user_msg)

        ai_msg = MockMessage(
            "This is an AI response to message {}. Here are the key points: "
            "First, it's important to understand the fundamentals. "
            "Second, you should consider the practical applications. "
            "Third, best practices include thorough testing and documentation. "
            "Finally, remember to iterate based on feedback.".format(i),
            'assistant'
        )
        messages.append(ai_msg)

    # Count tokens before
    tokens_before = count_tokens_simple(messages)
    messages_before = len(messages)

    print("  Before: {} messages, {} tokens (estimated)".format(messages_before, tokens_before))

    # Apply compression if over threshold
    if tokens_before > threshold:
        compressed = compress_messages(messages, keep_recent)
        tokens_after = count_tokens_simple(compressed)
        messages_after = len(compressed)

        reduction_pct = ((tokens_before - tokens_after) / float(tokens_before)) * 100

        print("  After:  {} messages, {} tokens (estimated)".format(messages_after, tokens_after))
        print("  Reduction: {:.1f}% tokens, {} messages removed".format(
            reduction_pct, messages_before - messages_after))

        return {
            'compressed': True,
            'messages_before': messages_before,
            'messages_after': messages_after,
            'tokens_before': tokens_before,
            'tokens_after': tokens_after,
            'reduction_pct': reduction_pct
        }
    else:
        print("  No compression needed: {} <= {}".format(tokens_before, threshold))
        return {
            'compressed': False,
            'messages_before': messages_before,
            'tokens_before': tokens_before
        }


def main():
    """Run compression tests"""
    print("="*70)
    print("Simple Compression Test (No Dependencies)")
    print("="*70)

    print("\n--- Phase 1: Testing different keep_recent values ---")
    print("Fixed: 50 message pairs (100 messages), threshold=5000")

    for keep_recent in [5, 10, 15, 20, 25]:
        test_compression(
            message_count=50,
            threshold=5000,
            keep_recent=keep_recent
        )

    print("\n--- Phase 2: Testing different thresholds ---")
    print("Fixed: 50 message pairs (100 messages), keep_recent=10")

    for threshold in [2000, 4000, 6000, 8000, 10000]:
        test_compression(
            message_count=50,
            threshold=threshold,
            keep_recent=10
        )

    print("\n--- Phase 3: Testing scaling behavior ---")
    print("Fixed: threshold=4000, keep_recent=10")

    for message_count in [10, 25, 50, 100, 200]:
        test_compression(
            message_count=message_count,
            threshold=4000,
            keep_recent=10
        )

    print("\n" + "="*70)
    print("Analysis:")
    print("="*70)
    print("1. Smaller keep_recent = more compression (higher reduction %)")
    print("2. Lower threshold = compression triggers earlier")
    print("3. Longer conversations = more opportunity for compression")
    print("\nRecommendation:")
    print("  - For quality: keep_recent >= 10 (preserve recent context)")
    print("  - For efficiency: threshold = 4000-6000 (balance between frequency and overhead)")
    print("="*70)


if __name__ == "__main__":
    main()
