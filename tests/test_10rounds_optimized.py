"""
Full 10-round test with optimization
"""
import sys
sys.path.insert(0, '.')

import time
import json
from pathlib import Path
from scenario_utils_v2 import create_baseline_agent, create_memory_v2_agent

llm_config = {
    "model": "deepseek-v4.1-flash",
    "api_key": "sk-e99121ac032b8e4d3e6717b3c6dbcd2ef267d2fa4f41339fb5b30851f2e0a17d",
    "base_url": "https://beeapi.dev/v1",
    "temperature": 0.7
}

print("="*70)
print("Scenario 1 - Optimized (10 rounds)")
print("="*70)

# Baseline
print("\n[1/2] Baseline...")
baseline_agent, baseline_tracker = create_baseline_agent(llm_config)
baseline_config = {"configurable": {"thread_id": f"opt-base-{int(time.time())}"}}

start = time.time()
baseline_agent.invoke({"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]}, baseline_config)
for i in range(2, 10):
    baseline_agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, baseline_config)
baseline_result = baseline_agent.invoke({"messages": [("user", "Remind me: what is my name and city?")]}, baseline_config)
baseline_time = time.time() - start

baseline_stats = baseline_tracker.get_stats()
print(f"  Done: {baseline_stats['total_tokens']:,} tokens in {baseline_time:.1f}s")

# Memory v2 optimized
print("\n[2/2] Memory v2 (optimized)...")
memory_agent, memory_tracker = create_memory_v2_agent(llm_config)
memory_config = {"configurable": {"thread_id": f"opt-mem-{int(time.time())}"}}

start = time.time()
memory_agent.invoke({"messages": [("user", "Hi! My name is Alice, I live in Beijing, and I love Python.")]}, memory_config)
for i in range(2, 10):
    memory_agent.invoke({"messages": [("user", f"Tell me about topic {i}.")]}, memory_config)
memory_result = memory_agent.invoke({"messages": [("user", "Remind me: what is my name and city?")]}, memory_config)
memory_time = time.time() - start

memory_stats = memory_tracker.get_stats()
print(f"  Done: {memory_stats['total_tokens']:,} tokens in {memory_time:.1f}s")

# Quality check
baseline_response = baseline_result['messages'][-1].content.lower()
memory_response = memory_result['messages'][-1].content.lower()
baseline_quality = (('alice' in baseline_response) + ('beijing' in baseline_response)) / 2.0 * 100
memory_quality = (('alice' in memory_response) + ('beijing' in memory_response)) / 2.0 * 100

# Results
diff = memory_stats['total_tokens'] - baseline_stats['total_tokens']
change = (diff / baseline_stats['total_tokens']) * 100
time_overhead = ((memory_time - baseline_time) / baseline_time) * 100

print("\n" + "="*70)
print("RESULTS")
print("="*70)
print(f"Baseline:  {baseline_stats['total_tokens']:>6,} tokens, {baseline_time:>5.1f}s, Quality: {baseline_quality:.0f}%")
print(f"Memory v2: {memory_stats['total_tokens']:>6,} tokens, {memory_time:>5.1f}s, Quality: {memory_quality:.0f}%")
print(f"Change:    {diff:>+6,} tokens ({change:+.1f}%), {time_overhead:+.1f}% time")
print()
print("Comparison:")
print(f"  v2 (before optimization): +31.4% overhead")
print(f"  v2 (after optimization):  {change:+.1f}%")
print()

if abs(change) < 5:
    print("Result: SUCCESS - Near zero overhead!")
elif change < -10:
    print("Result: BETTER THAN EXPECTED - Savings achieved!")
elif change < 20:
    print("Result: Small overhead, acceptable")
else:
    print("Result: Still has overhead, needs investigation")

print("="*70)

# Save result
result = {
    "scenario": "Scenario 1: Short (10 rounds) - Optimized",
    "version": "memory_v2.0_optimized",
    "rounds": 10,
    "timestamp": time.time(),
    "baseline": {
        "tokens": baseline_stats['total_tokens'],
        "requests": baseline_stats['total_requests'],
        "time": baseline_time
    },
    "memory_v2_optimized": {
        "tokens": memory_stats['total_tokens'],
        "requests": memory_stats['total_requests'],
        "time": memory_time
    },
    "comparison": {
        "token_difference": diff,
        "token_change_percent": change,
        "time_overhead_percent": time_overhead
    },
    "quality": {
        "baseline_percent": baseline_quality,
        "memory_v2_percent": memory_quality
    }
}

output_path = Path("test_results/scenario_1_short_v2_optimized.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\nSaved to: {output_path}")
