"""Multinode simultaneous scheduling test runner.

This test validates that the scheduler correctly handles multiple simultaneous
multinode jobs with different node counts.

Setup: 8 workers with concurrency=1 each

Test phases (each configuration uses all 8 workers):
- Phase 1: 4x 2-node tests (2n_a, 2n_b, 2n_c, 2n_d) = 8 workers
- Phase 2: 2x 4-node tests (4n_a, 4n_b) = 8 workers
- Phase 3: 2x 2-node + 1x 4-node (2n_a, 2n_b, 4n_a) = 4 + 4 = 8 workers

Each phase verifies that ALL tasks start simultaneously before any receive CONTINUE,
proving the scheduler correctly allocates workers for concurrent multinode execution.

Port allocation: 9200-9204
  - 9200: frontend (client-facing)
  - 9201: storage
  - 9202: scheduler (client gRPC)
  - 9203: scheduler (worker gRPC)
  - 9204: scheduler (admin HTTP)
  - 9886: socket server for test coordination
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

TEST_PORT = 9886
EXECUTOR_PORT = 9200
CONFIG_DIR = "_main/tests/multinode-simultaneous/config"

# Services for multinode simultaneous test: 8 worker/runner pairs with concurrency=1
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


def run_phase(
    ctx: TestContextWithSocket,
    phase_name: str,
    targets: list[str],
    expected_total_tasks: int,
) -> bool:
    """Run a test phase with multiple multinode tests.

    Args:
        ctx: Test context with workspace, output_base, and server
        phase_name: Description of this phase for logging
        targets: List of bazel test targets to run
        expected_total_tasks: Total number of tasks expected across all tests

    Returns:
        True if all tasks started and completed successfully, False otherwise.
    """
    print(f"\n{'='*60}")
    print(f"=== {phase_name} ===")
    print(f"{'='*60}")
    print(f"Targets: {targets}")
    print(f"Expected total tasks: {expected_total_tasks}")

    # Start bazel test (non-blocking)
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [f"//tests/multinode-simultaneous:{t}" for t in targets],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results", f"--jobs={len(targets)}"],
    )

    # Collect all STARTED messages
    print(f"\n--- Waiting for {expected_total_tasks} tasks to start ---")
    collected = run_and_collect_started(ctx.server, bazel_proc, expected_total_tasks)
    if collected is None:
        return False

    # Log which test IDs we received
    test_ids = [tid for tid in collected.test_ids if tid]
    print(f"\nReceived STARTED from: {sorted(test_ids)}")
    print(f"All {expected_total_tasks} tasks started simultaneously")

    # Send CONTINUE to all tasks
    print(f"\n--- Sending CONTINUE to all {expected_total_tasks} tasks ---")
    if not collected.continue_all():
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return False

    # Wait for bazel to finish
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return False

    print(f"PASS: {phase_name} completed successfully")
    return True


def test_multinode_simultaneous(ctx: TestContextWithSocket) -> int:
    """Run all multinode simultaneous scheduling tests."""
    print("\n" + "=" * 60)
    print("=== Multinode Simultaneous Scheduling Test ===")
    print("=" * 60)
    print("Testing scheduler's ability to handle multiple simultaneous")
    print("multinode jobs with different node configurations.")
    print("Each phase uses all 8 workers.")

    # Phase 1: 4x 2-node tests = 8 workers
    # Each 2-node test creates 2 tasks, so 4 tests = 8 tasks
    if not run_phase(
        ctx,
        phase_name="Phase 1: 4x 2-node tests",
        targets=["test_2n_a", "test_2n_b", "test_2n_c", "test_2n_d"],
        expected_total_tasks=8,  # 4 tests * 2 nodes each
    ):
        return 1

    # Phase 2: 2x 4-node tests = 8 workers
    # Each 4-node test creates 4 tasks, so 2 tests = 8 tasks
    if not run_phase(
        ctx,
        phase_name="Phase 2: 2x 4-node tests",
        targets=["test_4n_a", "test_4n_b"],
        expected_total_tasks=8,  # 2 tests * 4 nodes each
    ):
        return 1

    # Phase 3: 2x 2-node + 1x 4-node = 4 + 4 = 8 workers
    # 2 tests with 2 nodes + 1 test with 4 nodes = 4 + 4 = 8 tasks
    if not run_phase(
        ctx,
        phase_name="Phase 3: 2x 2-node + 1x 4-node",
        targets=["test_2n_a", "test_2n_b", "test_4n_a"],
        expected_total_tasks=8,  # 2*2 + 1*4 = 8
    ):
        return 1

    print("\n" + "=" * 60)
    print("=== All multinode simultaneous tests passed ===")
    print("=" * 60)
    print("Verified: Scheduler correctly handles multiple simultaneous")
    print("multinode jobs with different node configurations.")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-multinode-simultaneous-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_multinode_simultaneous,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
