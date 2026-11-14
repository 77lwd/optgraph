"""
Master Test Suite: Run all tests and generate comprehensive report
"""

import subprocess
import sys
import time


def run_test(test_file, description):
    """Run a test file and capture results"""
    print("\n" + "="*70)
    print(f"Running: {description}")
    print("="*70)

    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max per test
        )

        duration = time.time() - start_time

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        return {
            "test": description,
            "file": test_file,
            "success": result.returncode == 0,
            "duration": duration,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"[FAIL] Test timed out after {duration:.0f}s")
        return {
            "test": description,
            "file": test_file,
            "success": False,
            "duration": duration,
            "error": "Timeout"
        }

    except Exception as e:
        duration = time.time() - start_time
        print(f"[FAIL] Test failed: {e}")
        return {
            "test": description,
            "file": test_file,
            "success": False,
            "duration": duration,
            "error": str(e)
        }


def main():
    print("="*70)
    print("OptGraph Memory System: Comprehensive Test Suite")
    print("="*70)
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tests = [
        ("tests/test_stability.py", "Stability Test (10 runs)"),
        ("tests/test_long_conversation.py", "Long Conversation Test (50 rounds)"),
        ("tests/test_efficiency.py", "Efficiency Comparison"),
        ("tests/test_edge_cases.py", "Edge Cases Test"),
        ("tests/test_model_comparison.py", "Model Comparison"),
        ("tests/test_memory_overhead.py", "Memory Overhead Analysis"),
    ]

    results = []
    total_start = time.time()

    for test_file, description in tests:
        result = run_test(test_file, description)
        results.append(result)

    total_duration = time.time() - total_start

    # Final Summary
    print("\n\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)

    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed

    print(f"\nTotal tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")

    print("\nTest Results:")
    for r in results:
        status = "[OK] PASS" if r['success'] else "[FAIL] FAIL"
        print(f"  {status} {r['test']} ({r['duration']:.1f}s)")
        if 'error' in r:
            print(f"       Error: {r['error']}")

    # Save report
    report_file = f"test_report_{int(time.time())}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("OptGraph Memory System - Test Report\n")
        f.write("="*70 + "\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total duration: {total_duration:.1f}s\n\n")

        for r in results:
            f.write("\n" + "="*70 + "\n")
            f.write(f"Test: {r['test']}\n")
            f.write(f"File: {r['file']}\n")
            f.write(f"Status: {'PASS' if r['success'] else 'FAIL'}\n")
            f.write(f"Duration: {r['duration']:.1f}s\n")
            if 'error' in r:
                f.write(f"Error: {r['error']}\n")
            f.write("\nOutput:\n")
            f.write(r.get('stdout', ''))
            if r.get('stderr'):
                f.write("\nErrors:\n")
                f.write(r['stderr'])

    print(f"\nDetailed report saved to: {report_file}")
    print("="*70)


if __name__ == "__main__":
    main()
