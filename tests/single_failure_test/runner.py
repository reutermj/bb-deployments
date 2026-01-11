"""Test failure detection runner.

This test validates that bazel correctly detects when a test
binary fails (exits with non-zero status).

Test flow:
1. Start services
2. Run bazel test
3. Verify bazel test returns non-zero (failure detected)
"""

import sys

from lib.bazel_runner import run_bazel_test_sync
from lib.service_manager import default_services
from lib.test_runner import TestContext, run_test

EXECUTOR_PORT = 9010
CONFIG_DIR = "_main/tests/single_failure_test/config"


def test_failure_detection(ctx: TestContext) -> int:
    """Test that failed tests are correctly detected."""
    print("\n=== Running test failure detection test ===")

    result = run_bazel_test_sync(
        ctx.workspace,
        ctx.output_base,
        ["//tests/single_failure_test:test"],
        EXECUTOR_PORT,
    )

    if result.returncode == 0:
        print("FAIL: Bazel test should have failed but returned 0")
        return 1

    print(f"PASS: Bazel test correctly failed with code {result.returncode}")
    print("\n=== Test passed ===")
    print("Verified: Test runner correctly detects test failure")
    return 0


def main() -> int:
    return run_test(
        temp_prefix="bb-test-failure-",
        services=default_services(CONFIG_DIR),
        test_fn=test_failure_detection,
    )


if __name__ == "__main__":
    sys.exit(main())
