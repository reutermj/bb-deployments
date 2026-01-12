"""Multinode head-of-line blocking test runner.

This test validates that multinode jobs properly block at head-of-line,
preventing single-node jobs from being scheduled ahead of queued multinode jobs.

Setup:
- 2 workers (each with concurrency=1)
- 1 single-node test that gets scheduled first and blocks
- 1 two-node multinode test that queues but cannot be scheduled

Flow:
1. Submit a single-node job that immediately gets scheduled (uses 1 worker)
2. Wait for the single-node job to STARTED and block
3. Submit a 2-node multinode job that should queue (only 1 worker available)
4. Verify the multinode job does NOT get scheduled (head-of-line blocking)
5. Send CONTINUE to the single-node job (frees 1 worker -> 2 workers available)
6. Wait for the multinode job to get scheduled (both nodes STARTED)
7. Verify bazel exits successfully

This validates that:
- A queued multinode job blocks at head-of-line
- Single-node jobs cannot skip ahead of queued multinode jobs
- When enough workers become available, the multinode job gets scheduled

Port allocation: 9120-9125
  - 9120: frontend (client-facing)
  - 9121: storage
  - 9122: scheduler (client gRPC)
  - 9123: scheduler (worker gRPC)
  - 9124: scheduler (admin HTTP)
  - 9125: socket server for test coordination
"""

import sys

from lib.bazel_runner import run_bazel_test
from lib.message_coordination import (
    expect_no_message,
    wait_for_started_messages,
)
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9125
EXECUTOR_PORT = 9120
CONFIG_DIR = "_main/tests/multinode-head-of-line-blocking/config"

# Services for head-of-line blocking test: 2 worker/runner pairs with concurrency=1
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


def test_head_of_line_blocking(ctx: TestContextWithSocket) -> int:
    """Run the head-of-line blocking test."""
    print("\n=== Running multinode head-of-line blocking test ===")
    print("Testing that multinode jobs block at head-of-line")
    print("Setup: 2 workers, 1 single-node job, 1 two-node multinode job")

    # Step 1: Start single-node job (should get scheduled immediately)
    print("\n--- Step 1: Starting single-node job ---")
    single_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/multinode-head-of-line-blocking:test_single"],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Wait for single-node job to start
    print("Waiting for single-node job to start...")
    single_started = wait_for_started_messages(ctx.server, 1, timeout=60)
    if single_started is None:
        single_proc.terminate()
        return 1

    print("Single-node job started (blocking on worker 1)")

    # Step 2: Start multinode job (should queue, only 1 worker available)
    print("\n--- Step 2: Starting 2-node multinode job ---")
    multi_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/multinode-head-of-line-blocking:test_multi"],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Step 3: Verify multinode job does NOT get scheduled (head-of-line blocking)
    print("\n--- Step 3: Verifying multinode job is blocked ---")
    print("Waiting 5 seconds to confirm no STARTED message from multinode job...")
    if not expect_no_message(
        ctx.server,
        timeout=5.0,
        description="multinode job STARTED (should be blocked)",
    ):
        print("FAIL: Multinode job was scheduled when it should have been blocked!")
        single_proc.terminate()
        multi_proc.terminate()
        return 1

    print("PASS: Multinode job is properly blocked (head-of-line blocking working)")

    # Step 4: Continue the single-node job (frees worker 1)
    print("\n--- Step 4: Continuing single-node job ---")
    if not single_started.continue_all():
        print("FAIL: Could not send CONTINUE to single-node job")
        single_proc.terminate()
        multi_proc.terminate()
        return 1

    print("Single-node job continued, waiting for it to complete...")

    # Wait for single-node bazel to finish
    single_proc.wait()
    if single_proc.returncode != 0:
        print(f"FAIL: Single-node bazel test failed with code {single_proc.returncode}")
        multi_proc.terminate()
        return 1

    print("Single-node job completed, both workers now available")

    # Step 5: Wait for multinode job to get scheduled
    print("\n--- Step 5: Waiting for multinode job to start ---")
    multi_started = wait_for_started_messages(
        ctx.server, 2, timeout=60, expected_prefix="STARTED"
    )
    if multi_started is None:
        print("FAIL: Multinode job did not get scheduled after workers became available")
        multi_proc.terminate()
        return 1

    print("Multinode job started (both nodes running)")

    # Wait for multinode bazel to finish
    print("\n--- Waiting for multinode job to complete ---")
    multi_proc.wait()
    if multi_proc.returncode != 0:
        print(f"FAIL: Multinode bazel test failed with code {multi_proc.returncode}")
        return 1

    print("\nPASS: Multinode head-of-line blocking test passed")
    print("\n=== Test Summary ===")
    print("1. Single-node job was scheduled immediately (1 worker used)")
    print("2. Multinode job was properly blocked (needed 2 workers, only 1 free)")
    print("3. After single-node completed, multinode job was scheduled")
    print("4. Both jobs completed successfully")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-multinode-hol-blocking-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_head_of_line_blocking,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
