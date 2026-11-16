"""
Ultra-minimal test: Just 5 rounds to test optimization quickly
If this works, we scale up to 10 rounds
"""
import sys
sys.path.insert(0, '.')

import time
from scenario_utils_v2 import create_baseline_agent, create_memory_v2_agent

llm_config = {
    "model": "deepseek-v4.1-flash",
    "api_key": "sk-c402ad904411957b5990d1df4f91da4dbd3e9ae8d57f93ca2172c5d98122ba07",
    "base_url": "https://beeapi.dev/v1",
    "temperature": 0.7
}

print("Mini test: 5 rounds (optimized v2 should NOT compress)")
print("="*70)

# Test 1: Baseline
print("\n[1/2] Baseline (5 rounds)...")
baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
baseline_config = {"configurable": {"thread_id": f"mini-base-{int(time.time())}"}}

try:
    baseline_agent.invoke({"messages": [("user", "Hi! I'm Alice from Beijing.")]}, baseline_config)
    for i in range(2, 6):
        baseline_agent.invoke({"messages": [("user", f"Q{i}")]}, baseline_config)

    baseline_stats = baseline_tracker.get_stats()
    print(f"Baseline: {baseline_stats['total_tokens']:,} tokens, {baseline_stats['total_requests']} requests")
except Exception as e:
    print(f"FAILED: {e}")
    exit(1)

# Test 2: Memory v2 optimized
print("\n[2/2] Memory v2 optimized (5 rounds)...")
memory_agent, memory_tracker = create_memory_v2_agent(llm_config)
memory_config = {"configurable": {"thread_id": f"mini-mem-{int(time.time())}"}}

try:
    memory_agent.invoke({"messages": [("user", "Hi! I'm Alice from Beijing.")]}, memory_config)
    for i in range(2, 6):
        memory_agent.invoke({"messages": [("user", f"Q{i}")]}, memory_config)

    memory_stats = memory_tracker.get_stats()
    print(f"Memory v2: {memory_stats['total_tokens']:,} tokens, {memory_stats['total_requests']} requests")
except Exception as e:
    print(f"FAILED: {e}")
    exit(1)

# Compare
diff = memory_stats['total_tokens'] - baseline_stats['total_tokens']
change = (diff / baseline_stats['total_tokens']) * 100

print("\n" + "="*70)
print(f"Baseline:  {baseline_stats['total_tokens']:,} tokens")
print(f"Memory v2: {memory_stats['total_tokens']:,} tokens")
print(f"Change:    {diff:+,} tokens ({change:+.1f}%)")
print()

if abs(change) < 10:
    print("Result: SUCCESS - Near zero overhead!")
else:
    print(f"Result: Overhead detected ({change:+.1f}%)")

print("="*70)
