"""Multinode scheduling test runner.

This test validates scheduling of multiple 2-node multinode tests with limited workers.

Setup:
- 2 workers (each with concurrency=1)
- 2 two-node tests scheduled via a single bazel command

Flow:
1. Schedule both 2-node tests with a single bazel test command
2. Wait for the first 2-node test (TEST_ID=1) to have both nodes STARTED
3. Send CONTINUE to both nodes of the first test
4. Wait for the second 2-node test (TEST_ID=2) to have both nodes STARTED
5. Send CONTINUE to both nodes of the second test
6. Verify bazel exits successfully

This validates that:
- Multiple multinode tests can be scheduled together
- The scheduler properly handles multinode task grouping
- Workers become available for the second test after the first completes

Port allocation: 9110-9114
  - 9110: frontend (client-facing)
  - 9111: storage
  - 9112: scheduler (client gRPC)
  - 9113: scheduler (worker gRPC)
  - 9114: scheduler (admin HTTP)
  - 9886: socket server for test coordination
"""

import sys

from lib.bazel_runner import run_bazel_test
from lib.message_coordination import wait_for_test_group
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9886
EXECUTOR_PORT = 9110
CONFIG_DIR = "_main/tests/multinode-scheduling/config"

# Services for multinode scheduling test: 2 worker/runner pairs with concurrency=1
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker1", f"{CONFIG_DIR}/worker1.jsonnet", BINARY_WORKER),
    ServiceConfig("runner1", f"{CONFIG_DIR}/runner1.jsonnet", BINARY_RUNNER),
    ServiceConfig("worker2", f"{CONFIG_DIR}/worker2.jsonnet", BINARY_WORKER),
    ServiceConfig("runner2", f"{CONFIG_DIR}/runner2.jsonnet", BINARY_RUNNER),
]

# Extra directories for the 2 workers
EXTRA_DIRS = [
    "worker1",
    "worker1/build",
    "worker1/cache",
    "worker2",
    "worker2/build",
    "worker2/cache",
]


def test_multinode_scheduling(ctx: TestContextWithSocket) -> int:
    """Run the multinode scheduling test."""
    print("\n=== Running multinode scheduling test ===")
    print("Testing that 2 two-node tests can be scheduled with 2 workers")
    print("Both tests are scheduled via single bazel command, processed sequentially")

    # Start bazel test (non-blocking) - schedules both 2-node tests
    print("\n--- Starting bazel test with both 2-node tests ---")
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [
            "//tests/multinode-scheduling:test_2node_1",
            "//tests/multinode-scheduling:test_2node_2",
        ],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Wait for first 2-node test (TEST_ID=1) to start
    print("\n--- Waiting for test 1 (2 nodes) to start ---")
    test1_group = wait_for_test_group(ctx.server, "1", count=2, timeout=60)
    if test1_group is None:
        bazel_proc.terminate()
        return 1

    print("Test 1: Both nodes started")

    # Continue the first test
    print("--- Sending CONTINUE to test 1 ---")
    if not test1_group.continue_all():
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return 1

    print("Test 1: Continued, workers should become available")

    # Wait for second 2-node test (TEST_ID=2) to start
    print("\n--- Waiting for test 2 (2 nodes) to start ---")
    test2_group = wait_for_test_group(ctx.server, "2", count=2, timeout=60)
    if test2_group is None:
        bazel_proc.terminate()
        return 1

    print("Test 2: Both nodes started")

    # Continue the second test
    print("--- Sending CONTINUE to test 2 ---")
    if not test2_group.continue_all():
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return 1

    print("Test 2: Continued")

    # Wait for bazel to finish
    print("\n--- Waiting for bazel to complete ---")
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return 1

    print("\nPASS: Both 2-node tests completed successfully")
    print("\n=== Multinode scheduling test passed ===")
    print("Verified: Multiple multinode tests can be scheduled and run sequentially")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-multinode-scheduling-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_multinode_scheduling,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
