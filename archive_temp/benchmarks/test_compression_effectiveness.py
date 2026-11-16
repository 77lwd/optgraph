"""
Test compression effectiveness directly without API calls

Tests the compression logic itself by simulating long message histories
and measuring token reduction. This is faster, cheaper, and more accurate
than running real conversations.
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from optgraph.checkpointer import AdaptiveCheckpointSaver
import json
from datetime import datetime


def generate_mock_messages(count):
    """Generate mock message history

    Args:
        count: Number of message pairs to generate

    Returns:
        List of alternating user/assistant messages
    """
    messages = []

    # Add system message
    messages.append(SystemMessage(content="You are a helpful AI assistant."))

    topics = [
        "Python programming language and its ecosystem",
        "Machine learning fundamentals and applications",
        "Web development with modern frameworks",
        "Database design and optimization strategies",
        "Cloud computing and serverless architectures",
        "API design patterns and best practices",
        "Software testing methodologies and tools",
        "DevOps practices and CI/CD pipelines",
        "Security vulnerabilities and mitigation techniques",
        "Distributed systems and microservices architecture",
        "Data structures and algorithm complexity analysis",
        "Functional programming paradigms and concepts",
        "Mobile app development platforms and frameworks",
        "Version control systems and collaboration workflows",
        "Performance optimization and profiling techniques"
    ]

    for i in range(count):
        topic = topics[i % len(topics)]

        # User message
        user_msg = HumanMessage(
            content="Can you explain {}? I'm particularly interested in practical applications and common pitfalls.".format(topic)
        )
        messages.append(user_msg)

        # Assistant message (simulated long response)
        ai_msg = AIMessage(
            content="Certainly! {} is an important concept in software development. "
                    "Here are the key points: First, it provides significant benefits for scalability and maintainability. "
                    "Second, you need to consider the trade-offs between complexity and performance. "
                    "Third, common pitfalls include over-engineering and premature optimization. "
                    "In practice, you should start simple and iterate based on actual requirements. "
                    "Best practices include thorough testing, clear documentation, and following established patterns. "
                    "The community has developed excellent tools and libraries to help with this. "
                    "Would you like me to dive deeper into any specific aspect?".format(topic)
        )
        messages.append(ai_msg)

    return messages


def count_tokens(messages):
    """Count total tokens in messages using checkpointer's method

    Args:
        messages: List of messages

    Returns:
        Total token count
    """
    # Use a temporary checkpointer just for token counting
    temp_checkpointer = AdaptiveCheckpointSaver()
    return temp_checkpointer._count_tokens(messages)


def test_compression_with_params(message_count, threshold, keep_recent):
    """Test compression with specific parameters

    Args:
        message_count: Number of message pairs to generate
        threshold: Compression threshold
        keep_recent: Number of recent messages to keep

    Returns:
        Dict with test results
    """
    print("\n[Test] messages={}, threshold={}, keep_recent={}".format(message_count, threshold, keep_recent))

    # Generate messages
    messages = generate_mock_messages(message_count)
    tokens_before = count_tokens(messages)
    messages_before = len(messages)

    print("  Initial: {} messages, {} tokens".format(messages_before, tokens_before))

    # Create checkpointer and test compression
    checkpointer = AdaptiveCheckpointSaver(
        threshold=threshold,
        keep_recent=keep_recent
    )

    # Simulate compression trigger
    if tokens_before > threshold:
        compressed_messages = checkpointer._compress(messages)
        tokens_after = count_tokens(compressed_messages)
        messages_after = len(compressed_messages)

        reduction_pct = ((tokens_before - tokens_after) / float(tokens_before)) * 100

        print("  Compressed: {} messages, {} tokens".format(messages_after, tokens_after))
        print("  Reduction: {:.1f}% tokens, {} messages removed".format(reduction_pct, messages_before - messages_after))

        return {
            "message_count": message_count,
            "threshold": threshold,
            "keep_recent": keep_recent,
            "messages_before": messages_before,
            "messages_after": messages_after,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "token_reduction_pct": reduction_pct,
            "messages_removed": messages_before - messages_after,
            "compressed": True
        }
    else:
        print("  No compression: {} <= {}".format(tokens_before, threshold))
        return {
            "message_count": message_count,
            "threshold": threshold,
            "keep_recent": keep_recent,
            "messages_before": messages_before,
            "tokens_before": tokens_before,
            "compressed": False
        }


def find_optimal_keep_recent():
    """Phase 1: Find minimum keep_recent that preserves recent context

    Strategy: Test different keep_recent values with large message history
    to see compression effectiveness.
    """
    print("\n" + "="*70)
    print("Phase 1: Testing keep_recent values")
    print("="*70)

    results = []

    # Test with 50 message pairs (100 messages total)
    message_count = 50
    threshold = 5000  # Low enough to always trigger

    for keep_recent in [5, 10, 15, 20, 25]:
        result = test_compression_with_params(
            message_count=message_count,
            threshold=threshold,
            keep_recent=keep_recent
        )
        results.append(result)

    return results


def find_optimal_threshold(keep_recent):
    """Phase 2: Find optimal threshold for given keep_recent

    Strategy: Test different thresholds to see when compression triggers
    and how effective it is.
    """
    print("\n" + "="*70)
    print("Phase 2: Testing threshold values (keep_recent={})".format(keep_recent))
    print("="*70)

    results = []

    # Test with 50 message pairs
    message_count = 50

    for threshold in [2000, 4000, 6000, 8000, 10000]:
        result = test_compression_with_params(
            message_count=message_count,
            threshold=threshold,
            keep_recent=keep_recent
        )
        results.append(result)

    return results


def test_scaling_behavior(keep_recent, threshold):
    """Phase 3: Test how compression scales with conversation length

    Strategy: Test with increasing message counts to see compression
    effectiveness over time.
    """
    print("\n" + "="*70)
    print("Phase 3: Testing scaling (threshold={}, keep_recent={})".format(threshold, keep_recent))
    print("="*70)

    results = []

    for message_count in [10, 25, 50, 100, 200]:
        result = test_compression_with_params(
            message_count=message_count,
            threshold=threshold,
            keep_recent=keep_recent
        )
        results.append(result)

    return results


def main():
    """Run complete compression effectiveness test"""
    print("\n" + "="*70)
    print("Compression Effectiveness Test (No API Calls)")
    print("="*70)
    print("Start time: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "phase1_keep_recent": None,
        "phase2_threshold": None,
        "phase3_scaling": None
    }

    # Phase 1: Find good keep_recent value
    phase1_results = find_optimal_keep_recent()
    all_results["phase1_keep_recent"] = phase1_results

    # Analyze phase 1: pick keep_recent with best reduction
    compressed_results = [r for r in phase1_results if r.get("compressed")]
    if compressed_results:
        best = max(compressed_results, key=lambda x: x["token_reduction_pct"])
        optimal_keep_recent = best["keep_recent"]
        print("\n[Phase 1 Result] Best keep_recent: {} ({:.1f}% reduction)".format(
            optimal_keep_recent, best['token_reduction_pct']))
    else:
        optimal_keep_recent = 10  # Default fallback
        print("\n[Phase 1 Result] No compression triggered, using default: {}".format(optimal_keep_recent))

    # Phase 2: Find optimal threshold
    phase2_results = find_optimal_threshold(optimal_keep_recent)
    all_results["phase2_threshold"] = phase2_results

    # Analyze phase 2: pick threshold with best reduction
    compressed_results = [r for r in phase2_results if r.get("compressed")]
    if compressed_results:
        best = max(compressed_results, key=lambda x: x["token_reduction_pct"])
        optimal_threshold = best["threshold"]
        print("\n[Phase 2 Result] Best threshold: {} ({:.1f}% reduction)".format(
            optimal_threshold, best['token_reduction_pct']))
    else:
        optimal_threshold = 4000  # Default fallback
        print("\n[Phase 2 Result] No good threshold found, using default: {}".format(optimal_threshold))

    # Phase 3: Test scaling
    phase3_results = test_scaling_behavior(optimal_keep_recent, optimal_threshold)
    all_results["phase3_scaling"] = phase3_results

    # Final recommendation
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print("Recommended keep_recent: {}".format(optimal_keep_recent))
    print("Recommended threshold: {}".format(optimal_threshold))

    # Show scaling analysis
    print("\nScaling Analysis:")
    for result in phase3_results:
        if result.get("compressed"):
            print("  {} msg pairs: {:.1f}% reduction, {} messages removed".format(
                result['message_count'],
                result['token_reduction_pct'],
                result['messages_removed']))
        else:
            print("  {} msg pairs: No compression".format(result['message_count']))

    # Save results
    output_file = "benchmarks/compression_effectiveness_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print("\nResults saved to: {}".format(output_file))
    print("="*70)


if __name__ == "__main__":
    main()
