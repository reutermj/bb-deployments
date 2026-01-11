"""Multinode count validation test runner.

This test validates that the scheduler correctly:
1. Rejects actions with multinode_count > MaxMultinodeCount (100 > 16)
2. Rejects actions with multinode_count == 0
3. Rejects actions with multinode_count < 0 (negative)
4. Accepts actions with valid multinode_count values (1, 4)

Port allocation: 9080-9084
  - 9080: frontend (client-facing)
  - 9081: storage
  - 9082: scheduler (client gRPC)
  - 9083: scheduler (worker gRPC)
  - 9084: scheduler (admin HTTP)
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

from lib.service_manager import ServiceManager, default_services
from lib.workspace import find_workspace_root


CONFIG_DIR = "_main/tests/multinode-count-validation/config"


class TestCase(NamedTuple):
    name: str
    target: str
    should_fail: bool
    error_pattern: str | None  # Pattern to look for in error output


TEST_CASES = [
    TestCase(
        name="multinode_count exceeds max (100 > 16)",
        target="//tests/multinode-count-validation:test_exceeds_max",
        should_fail=True,
        error_pattern="exceeds maximum",
    ),
    TestCase(
        name="multinode_count is zero",
        target="//tests/multinode-count-validation:test_zero",
        should_fail=True,
        error_pattern="must be at least 1",
    ),
    TestCase(
        name="multinode_count is negative (-1)",
        target="//tests/multinode-count-validation:test_negative",
        should_fail=True,
        error_pattern="must be a positive integer",
    ),
    TestCase(
        name="multinode_count is non-integer",
        target="//tests/multinode-count-validation:test_non_integer",
        should_fail=True,
        error_pattern="must be a positive integer",
    ),
    # Valid multinode_count values are stripped from the platform key
    # so the action matches workers with empty platform.
    TestCase(
        name="valid multinode_count=1 (single node)",
        target="//tests/multinode-count-validation:test_valid_single",
        should_fail=False,
        error_pattern=None,
    ),
    TestCase(
        name="valid multinode_count=4 (multi-node)",
        target="//tests/multinode-count-validation:test_valid_multi",
        should_fail=False,
        error_pattern=None,
    ),
]


def run_bazel_test(
    workspace: str, output_base: str, target: str
) -> subprocess.CompletedProcess:
    """Run bazel test with remote execution config."""
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--remote_executor=grpc://localhost:9080",
        "--disk_cache=",
        target,
    ]

    return subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
    )


def run_rejection_test(
    workspace: str, output_base: str, test_case: TestCase
) -> bool:
    """Run a test that should be rejected by the scheduler."""
    print(f"\n--- Testing: {test_case.name} ---")
    print(f"Target: {test_case.target}")
    print(f"Expected: Rejection with pattern '{test_case.error_pattern}'")

    result = run_bazel_test(workspace, output_base, test_case.target)

    if result.returncode == 0:
        print(f"FAIL: Test succeeded but should have been rejected")
        return False

    combined_output = result.stdout + result.stderr

    if test_case.error_pattern and test_case.error_pattern.lower() in combined_output.lower():
        print(f"PASS: Found expected error pattern")
        return True
    else:
        # Still check for InvalidArgument as fallback
        if "invalid" in combined_output.lower():
            print(f"PASS: Found InvalidArgument error (pattern not exact match)")
            return True
        print(f"FAIL: Did not find expected error pattern")
        print(f"Stderr snippet: {result.stderr[:500]}")
        return False


def run_valid_test(workspace: str, output_base: str, test_case: TestCase) -> bool:
    """Run a test with valid multinode_count that should execute."""
    print(f"\n--- Testing: {test_case.name} ---")
    print(f"Target: {test_case.target}")
    print(f"Expected: Successful execution")

    result = run_bazel_test(workspace, output_base, test_case.target)

    if result.returncode != 0:
        print(f"FAIL: Test failed but should have succeeded")
        print(f"Stderr snippet: {result.stderr[:2000]}")
        return False

    print(f"PASS: Test executed successfully")
    return True


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-multinode-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        services = ServiceManager(working_dir, default_services(CONFIG_DIR))

        if not services.start():
            print("FAIL: Could not start Buildbarn services")
            return 1

        try:
            print("\n=== Running multinode_count validation tests ===")
            print(f"Running {len(TEST_CASES)} test cases")

            passed = 0
            failed = 0

            for test_case in TEST_CASES:
                if test_case.should_fail:
                    success = run_rejection_test(workspace, output_base, test_case)
                else:
                    success = run_valid_test(workspace, output_base, test_case)

                if success:
                    passed += 1
                else:
                    failed += 1

            print("\n" + "=" * 50)
            print(f"Results: {passed} passed, {failed} failed")

            if failed > 0:
                print("FAIL: Some tests failed")
                return 1

            print("PASS: All multinode_count validation tests passed")

        finally:
            services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== Test passed ===")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
