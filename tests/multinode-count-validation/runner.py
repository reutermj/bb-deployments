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

from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
    ServiceManager,
)
from lib.workspace import find_workspace_root


CONFIG_DIR = "_main/tests/multinode-count-validation/config"

# Services for multinode validation test: 4 worker/runner pairs
# to support multinode_count=4 tests
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
]

# Add 4 worker/runner pairs
for i in range(1, 5):
    SERVICES.append(
        ServiceConfig(f"worker{i}", f"{CONFIG_DIR}/worker{i}.jsonnet", BINARY_WORKER)
    )
    SERVICES.append(
        ServiceConfig(f"runner{i}", f"{CONFIG_DIR}/runner{i}.jsonnet", BINARY_RUNNER)
    )

# Extra directories for the 4 workers
EXTRA_DIRS = []
for i in range(1, 5):
    EXTRA_DIRS.extend([f"worker{i}", f"worker{i}/build", f"worker{i}/cache"])


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
        "--test_timeout=30",
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
        services = ServiceManager(working_dir, SERVICES, EXTRA_DIRS)

        if not services.start():
            print("FAIL: Could not start Buildbarn services")
            return 1

        try:
            print("\n=== Running multinode_count validation tests ===")
            print(f"Running {len(TEST_CASES)} test cases")

            for test_case in TEST_CASES:
                if test_case.should_fail:
                    success = run_rejection_test(workspace, output_base, test_case)
                else:
                    success = run_valid_test(workspace, output_base, test_case)

                if not success:
                    print(f"\nFAIL: Test '{test_case.name}' failed - aborting")
                    return 1

            print("\n" + "=" * 50)
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
