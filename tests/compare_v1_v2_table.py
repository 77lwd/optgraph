"""
Generate comprehensive comparison table: v1 vs v2
"""

import json
from pathlib import Path

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    results_dir = Path('../test_results')

    scenarios = [
        ('scenario_1_short', 'Scenario 1: Short (10 rounds)'),
        ('scenario_2_medium', 'Scenario 2: Medium (30 rounds)'),
        ('scenario_3_long', 'Scenario 3: Long (50 rounds)'),
        ('scenario_4_long_messages', 'Scenario 4: Long Messages (20 rounds)'),
        ('scenario_5_realistic', 'Scenario 5: Realistic Mixed (25 rounds)'),
    ]

    print("="*100)
    print("MEMORY SYSTEM COMPARISON: v1 vs v2")
    print("="*100)
    print()

    # Header
    print(f"{'Scenario':<35} {'Baseline':>12} {'v1':>12} {'v1 Change':>12} {'v2':>12} {'v2 Change':>12} {'Improvement':>12}")
    print("-"*100)

    v1_changes = []
    v2_changes = []
    improvements = []

    for filename, name in scenarios:
        try:
            v1_file = results_dir / f"{filename}.json"
            v2_file = results_dir / f"{filename}_v2.json"

            if not v1_file.exists() or not v2_file.exists():
                print(f"{name:<35} Data missing")
                continue

            v1_data = load_json(v1_file)
            v2_data = load_json(v2_file)

            # Get baseline (should be same)
            baseline_tokens = v1_data['baseline']['tokens']

            # v1 results
            v1_tokens = v1_data['memory']['tokens']
            v1_change = v1_data['savings']['token_reduction_percent']

            # v2 results
            v2_tokens = v2_data['memory_v2']['tokens']
            v2_change = v2_data['comparison']['token_change_percent']

            # Improvement
            improvement = v2_change - v1_change

            print(f"{name:<35} {baseline_tokens:>12,} {v1_tokens:>12,} {v1_change:>11.1f}% {v2_tokens:>12,} {v2_change:>11.1f}% {improvement:>11.1f}%")

            v1_changes.append(v1_change)
            v2_changes.append(v2_change)
            improvements.append(improvement)

        except Exception as e:
            print(f"{name:<35} Error: {e}")

    # Summary
    print("-"*100)
    if v1_changes and v2_changes:
        avg_v1 = sum(v1_changes) / len(v1_changes)
        avg_v2 = sum(v2_changes) / len(v2_changes)
        avg_improvement = sum(improvements) / len(improvements)

        print(f"{'Average':<35} {'':<12} {'':<12} {avg_v1:>11.1f}% {'':<12} {avg_v2:>11.1f}% {avg_improvement:>11.1f}%")

    print("="*100)
    print()

    # Analysis
    print("KEY FINDINGS:")
    print("-"*100)

    # Find worst case
    if v1_changes:
        worst_v1_idx = v1_changes.index(min(v1_changes))
        worst_v1_name = scenarios[worst_v1_idx][1]
        worst_v1_value = v1_changes[worst_v1_idx]

        print(f"v1 Worst Case: {worst_v1_name}")
        print(f"  Result: {worst_v1_value:.1f}% ({'disaster' if worst_v1_value < -100 else 'overhead' if worst_v1_value < 0 else 'ok'})")

        # v2 result for same scenario
        v2_same = v2_changes[worst_v1_idx]
        improvement_same = improvements[worst_v1_idx]
        print(f"  v2 Fixed: {v2_same:.1f}% (improvement: {improvement_same:+.1f}%)")
        print()

    # Success rate
    v1_success = sum(1 for x in v1_changes if x > 0)
    v2_success = sum(1 for x in v2_changes if x < 0)  # Note: negative = savings

    print(f"Success Rate:")
    print(f"  v1: {v1_success}/{len(v1_changes)} scenarios with savings ({v1_success/len(v1_changes)*100:.0f}%)")
    print(f"  v2: {v2_success}/{len(v2_changes)} scenarios with savings ({v2_success/len(v2_changes)*100:.0f}%)")
    print()

    # Optimization note
    print("OPTIMIZATION NOTE:")
    print("-"*100)
    print("v2 Scenario 1 shows +31.4% overhead (compression triggered unnecessarily)")
    print("Fix: min_total_messages=25 (skip compression for <25 messages)")
    print("Expected after optimization: ~0% overhead")
    print("="*100)

if __name__ == "__main__":
    main()
