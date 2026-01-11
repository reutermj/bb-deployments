"""Multinode concurrency test runner.

This test validates that with 8 workers (each with concurrency=1),
a multinode job with multinode_count=N creates N tasks that run
on N different workers simultaneously.

The test schedules a single multinode job and verifies that ALL N
tasks send STARTED before any receives CONTINUE. This proves they
are running concurrently on different workers.

Port allocation: 9100-9104
  - 9100: frontend (client-facing)
  - 9101: storage
  - 9102: scheduler (client gRPC)
  - 9103: scheduler (worker gRPC)
  - 9104: scheduler (admin HTTP)
  - 9885: socket server for test coordination
"""

import sys

from lib.bazel_runner import run_bazel_test
from lib.message_coordination import run_and_collect_started
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9885
EXECUTOR_PORT = 9100
CONFIG_DIR = "_main/tests/multinode-concurrency/config"

# Services for multinode concurrency test: 8 worker/runner pairs with concurrency=1
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
]

# Add 8 worker/runner pairs
for i in range(1, 9):
    SERVICES.append(
        ServiceConfig(f"worker{i}", f"{CONFIG_DIR}/worker{i}.jsonnet", BINARY_WORKER)
    )
    SERVICES.append(
        ServiceConfig(f"runner{i}", f"{CONFIG_DIR}/runner{i}.jsonnet", BINARY_RUNNER)
    )

# Extra directories for the 8 workers
EXTRA_DIRS = []
for i in range(1, 9):
    EXTRA_DIRS.extend([f"worker{i}", f"worker{i}/build", f"worker{i}/cache"])


def test_multinode_concurrent_execution(
    ctx: TestContextWithSocket, multinode_count: int
) -> bool:
    """Test that a multinode job with N tasks runs N tasks concurrently.

    Returns True if all N tasks started concurrently, False otherwise.
    """
    print(f"\n=== Testing multinode_count={multinode_count} ===")
    print(
        f"With 8 workers (concurrency=1 each), all {multinode_count} tasks should start simultaneously"
    )

    # Start bazel test (non-blocking)
    target = f"//tests/multinode-concurrency:test_multinode_{multinode_count}"
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [target],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Collect all STARTED messages
    print(f"\n--- Waiting for {multinode_count} tasks to start ---")
    collected = run_and_collect_started(ctx.server, bazel_proc, multinode_count)
    if collected is None:
        return False

    print(f"\nAll {multinode_count} tasks started - verified concurrent execution")

    # Now send CONTINUE to all tasks
    print(f"\n--- Sending CONTINUE to all {multinode_count} tasks ---")
    if not collected.continue_all():
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return False

    # Wait for bazel to finish
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return False

    print(f"PASS: {multinode_count} multinode tasks ran concurrently")
    return True


def test_multinode_concurrency(ctx: TestContextWithSocket) -> int:
    """Run all multinode concurrency tests."""
    print("\n=== Running multinode concurrency tests ===")
    print("Testing that multinode jobs run tasks concurrently on different workers")

    # Test with 2, 4, and 8 multinode tasks
    for multinode_count in [2, 4, 8]:
        if not test_multinode_concurrent_execution(ctx, multinode_count):
            return 1

    print("\n=== All multinode concurrency tests passed ===")
    print("Verified: Multinode jobs run tasks concurrently on different workers")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-multinode-concurrency-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_multinode_concurrency,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
