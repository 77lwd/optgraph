"""
View Summary of All Scenario Results

Usage:
    python tests/view_summary.py
"""

import sys
sys.path.insert(0, '.')

from scenario_utils import load_existing_results, print_summary


def main():
    print("="*70)
    print("Multi-Scenario Test Results Summary")
    print("="*70)
    print()

    # Load all results
    all_results = load_existing_results("test_results")

    if not all_results:
        print("No test results found yet.")
        print()
        print("Run individual scenario tests first:")
        print("  python tests/test_scenario_1_short.py")
        print("  python tests/test_scenario_2_medium.py")
        print("  python tests/test_scenario_3_long.py")
        print("  python tests/test_scenario_4_long_messages.py")
        print("  python tests/test_scenario_5_realistic.py")
        return

    print(f"Found {len(all_results)} completed scenario(s):\n")

    # Print summary
    print_summary(all_results)

    print("\nResult files saved in: test_results/")
    print()


if __name__ == "__main__":
    main()
