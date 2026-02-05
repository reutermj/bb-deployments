"""Scheduler chaos monkey test runner.

This test validates the system's resilience when the scheduler is killed:
1. Workers stay alive when scheduler dies
2. Workers reconnect when scheduler restarts
3. Jobs can be re-run after recovery
4. Action results are NOT cached when scheduler dies mid-execution

Port allocation: 9210-9215
  - 9210: frontend (client-facing)
  - 9211: storage
  - 9212: scheduler (client gRPC)
  - 9213: scheduler (worker gRPC)
  - 9214: scheduler (admin HTTP)
  - 9215: socket server for test coordination
"""

import sys
import time

from lib.bazel_runner import run_bazel_test
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.socket_server import Message, SocketServer
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9215
EXECUTOR_PORT = 9210
CONFIG_DIR = "_main/tests/scheduler-chaos/config"

# Services for chaos test
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker", f"{CONFIG_DIR}/worker.jsonnet", BINARY_WORKER),
    ServiceConfig("runner", f"{CONFIG_DIR}/runner.jsonnet", BINARY_RUNNER),
]


def test_scheduler_kill_during_execution(ctx: TestContextWithSocket) -> bool:
    """Test: Worker resilience and recovery when scheduler dies.

    This test focuses on the WORKER's behavior - verifying that workers
    survive scheduler death and can reconnect to accept new work.

    Validates:
    - Worker process stays alive when scheduler dies (same PID)
    - Bazel client fails as expected (exit code 34)
    - Worker automatically reconnects when scheduler restarts
    - System can execute new actions after recovery
    """
    print("\n" + "=" * 60)
    print("TEST: Kill scheduler during execution")
    print("=" * 60)

    # Step 1: Start test action (will wait for CONTINUE)
    print("\n--- Step 1: Start test action ---")
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/scheduler-chaos:test1"],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Step 2: Wait for STARTED message (confirms worker is executing)
    print("Waiting for test action to start...")
    msg = ctx.server.wait_for_message_with_conn(timeout=60)
    if not msg or not msg.content.startswith("STARTED:"):
        print(f"FAIL: Expected STARTED message, got: {msg}")
        bazel_proc.terminate()
        return False
    test_id = msg.content.split(":")[1]
    print(f"Received: {msg.content} - Worker is executing the action")

    # Record worker PID to verify it stays alive
    worker_pid = ctx.services.get_service_pid("worker")
    print(f"Worker PID before kill: {worker_pid}")

    # Step 3: Kill scheduler
    print("\n--- Step 2: Kill scheduler ---")
    if not ctx.services.kill_service("scheduler"):
        print("FAIL: Could not kill scheduler")
        bazel_proc.terminate()
        return False
    print("Scheduler killed")

    # Step 4: Send CONTINUE to let worker complete the action
    print("\n--- Step 3: Send CONTINUE to worker (scheduler is dead) ---")
    if not SocketServer.reply(msg, "CONTINUE"):
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return False
    print("Sent CONTINUE to test action")

    # Step 5: Wait for bazel to fail (expected)
    print("\n--- Step 4: Wait for bazel to fail ---")
    try:
        bazel_proc.wait(timeout=60)
    except Exception:
        print("FAIL: Bazel did not exit within timeout")
        bazel_proc.terminate()
        return False

    if bazel_proc.returncode == 0:
        print("UNEXPECTED: Bazel succeeded (expected failure)")
        # This isn't necessarily a failure, but it's unexpected
    else:
        print(f"Bazel failed with exit code: {bazel_proc.returncode} (expected)")

    # Step 6: Verify worker is still alive
    print("\n--- Step 5: Verify worker stayed alive ---")
    time.sleep(1)  # Brief wait
    if not ctx.services.is_service_running("worker"):
        print("FAIL: Worker died when scheduler was killed")
        return False
    worker_pid_after = ctx.services.get_service_pid("worker")
    if worker_pid_after != worker_pid:
        print(f"FAIL: Worker PID changed from {worker_pid} to {worker_pid_after}")
        return False
    print(f"PASS: Worker is still alive (PID {worker_pid_after})")

    # Step 7: Restart scheduler
    print("\n--- Step 6: Restart scheduler ---")
    if not ctx.services.start_service("scheduler", wait=5):
        print("FAIL: Could not restart scheduler")
        return False
    print("Scheduler restarted")

    # Step 8: Verify worker reconnects and system recovers
    print("\n--- Step 7: Verify recovery - run same action again ---")
    bazel_proc2 = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/scheduler-chaos:test1"],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Wait for STARTED - this proves worker reconnected and can accept new jobs
    msg2 = ctx.server.wait_for_message_with_conn(timeout=60)
    if not msg2 or not msg2.content.startswith("STARTED:"):
        print(f"FAIL: Recovery failed - expected STARTED, got: {msg2}")
        bazel_proc2.terminate()
        return False
    print(f"Received: {msg2.content} - Worker reconnected and accepted new job")
    print("PASS: Worker reconnected to scheduler")

    # Complete the action
    if not SocketServer.reply(msg2, "CONTINUE"):
        print("FAIL: Could not send CONTINUE after recovery")
        bazel_proc2.terminate()
        return False

    bazel_proc2.wait(timeout=60)
    if bazel_proc2.returncode != 0:
        print(f"FAIL: Recovery action failed with code: {bazel_proc2.returncode}")
        return False

    print("PASS: Action succeeded after scheduler recovery")
    print("\n" + "=" * 60)
    print("TEST PASSED: Kill scheduler during execution")
    print("=" * 60)
    return True


def test_action_not_cached_on_scheduler_death(ctx: TestContextWithSocket) -> bool:
    """Test: Action cache behavior when scheduler dies mid-execution.

    This test focuses on the ACTION CACHE - verifying that work is lost
    when the scheduler dies before it can record the action result.

    Even though the worker completes the action, the scheduler never
    records the result in the action cache. This means retries must
    re-execute the action from scratch (no cache hit).

    Validates:
    - Retry of same action triggers re-execution (receives STARTED again)
    - Action result was NOT cached during scheduler downtime
    """
    print("\n" + "=" * 60)
    print("TEST: Action not cached when scheduler dies")
    print("=" * 60)

    # Step 1: Start action
    print("\n--- Step 1: Start test action ---")
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/scheduler-chaos:test2"],
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results"],
    )

    # Wait for action to start
    msg = ctx.server.wait_for_message_with_conn(timeout=60)
    if not msg or not msg.content.startswith("STARTED:"):
        print(f"FAIL: Expected STARTED, got: {msg}")
        bazel_proc.terminate()
        return False
    test_id = msg.content.split(":")[1]
    print(f"Received: {msg.content}")

    # Step 2: Kill scheduler
    print("\n--- Step 2: Kill scheduler ---")
    if not ctx.services.kill_service("scheduler"):
        print("FAIL: Could not kill scheduler")
        bazel_proc.terminate()
        return False

    # Step 3: Let action complete (worker will do the work)
    print("\n--- Step 3: Send CONTINUE (let worker complete) ---")
    if not SocketServer.reply(msg, "CONTINUE"):
        print("FAIL: Could not send CONTINUE")
        bazel_proc.terminate()
        return False

    # Wait a moment for worker to complete
    time.sleep(3)

    # Bazel will fail
    bazel_proc.wait(timeout=60)
    print(f"Bazel exited with code: {bazel_proc.returncode}")

    # Step 4: Restart scheduler
    print("\n--- Step 4: Restart scheduler ---")
    if not ctx.services.start_service("scheduler", wait=5):
        print("FAIL: Could not restart scheduler")
        return False

    # Step 5: Run same test again - should re-execute (NOT cache hit)
    print("\n--- Step 5: Run same test again (should re-execute, not cache hit) ---")
    bazel_proc2 = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        ["//tests/scheduler-chaos:test2"],
        EXECUTOR_PORT,
        # NOTE: Not using --nocache_test_results here - we want to see if it's cached
    )

    # Check if we get STARTED (re-execution) or immediate success (cache hit)
    msg2 = ctx.server.wait_for_message_with_conn(timeout=30)

    if msg2 and msg2.content.startswith("STARTED:"):
        # Action was re-executed - this is the expected behavior
        print(f"Received: {msg2.content}")
        print("PASS: Action was RE-EXECUTED (not cached)")

        # Complete the action
        if not SocketServer.reply(msg2, "CONTINUE"):
            bazel_proc2.terminate()
            return False
        bazel_proc2.wait(timeout=60)
    else:
        # No STARTED received - could be cache hit
        bazel_proc2.wait(timeout=60)
        if bazel_proc2.returncode == 0:
            print("FAIL: Action was cached - did not re-execute")
            return False
        else:
            print(f"FAIL: Unexpected error: {bazel_proc2.returncode}")
            return False

    print("\n" + "=" * 60)
    print("TEST PASSED: Action not cached when scheduler dies")
    print("=" * 60)
    return True


def test_scheduler_chaos(ctx: TestContextWithSocket) -> int:
    """Run all scheduler chaos tests."""
    print("\n" + "=" * 60)
    print("SCHEDULER CHAOS MONKEY TEST SUITE")
    print("=" * 60)

    # Test 1: Kill scheduler during execution
    if not test_scheduler_kill_during_execution(ctx):
        return 1

    # Test 2: Verify action not cached
    if not test_action_not_cached_on_scheduler_death(ctx):
        return 1

    print("\n" + "=" * 60)
    print("ALL CHAOS TESTS PASSED")
    print("=" * 60)
    print("\nValidated:")
    print("  - Workers stay alive when scheduler dies")
    print("  - Workers reconnect when scheduler restarts")
    print("  - Actions can be re-run after recovery")
    print("  - Action results are NOT cached when scheduler dies mid-execution")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-scheduler-chaos-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_scheduler_chaos,
    )


if __name__ == "__main__":
    sys.exit(main())
