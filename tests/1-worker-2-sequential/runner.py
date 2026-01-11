"""Sequential execution test runner.

This test validates that with a single worker (concurrency=1):
1. Both tests enter the queue and one starts on the worker
2. The first test sends STARTED, receives CONTINUE, then exits
3. The second test gets scheduled after the first completes
4. The second test sends STARTED, receives CONTINUE, then exits

The second STARTED message proves the first test completed and freed the worker.
"""

import sys

from lib.bazel_runner import run_bazel_test
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.socket_server import SocketServer
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9881
EXECUTOR_PORT = 9040
CONFIG_DIR = "_main/tests/1-worker-2-sequential/config"

# Services for sequential test: single worker with concurrency=1
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker", f"{CONFIG_DIR}/worker.jsonnet", BINARY_WORKER),
    ServiceConfig("runner", f"{CONFIG_DIR}/runner.jsonnet", BINARY_RUNNER),
]


def test_sequential_execution(ctx: TestContextWithSocket) -> int:
    """Test that tests run sequentially with single worker."""
    print("\n=== Running sequential execution test ===")
    print("Worker has concurrency=1, so tests must run one at a time")

    # Start bazel tests (non-blocking)
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [
            "//tests/1-worker-2-sequential:test1",
            "//tests/1-worker-2-sequential:test2",
        ],
        EXECUTOR_PORT,
        extra_flags=["--jobs=2"],
    )

    # === First test execution ===
    print("\n--- Waiting for first test to start ---")
    msg1 = ctx.server.wait_for_message_with_conn(60)
    if msg1 is None:
        print("FAIL: Timeout waiting for first STARTED message")
        bazel_proc.terminate()
        return 1
    if msg1.content != "STARTED":
        print(f"FAIL: Expected STARTED, got: {msg1.content}")
        bazel_proc.terminate()
        return 1
    print("PASS: First test started")

    # Send CONTINUE to first test (it will exit after receiving this)
    print("Sending CONTINUE to first test...")
    if not SocketServer.reply(msg1, "CONTINUE"):
        print("FAIL: Could not send CONTINUE to first test")
        bazel_proc.terminate()
        return 1

    # === Second test execution ===
    print("\n--- Waiting for second test to start ---")
    print("(This validates that the second test was queued and scheduled after the first)")
    msg2 = ctx.server.wait_for_message_with_conn(60)
    if msg2 is None:
        print("FAIL: Timeout waiting for second STARTED message")
        bazel_proc.terminate()
        return 1
    if msg2.content != "STARTED":
        print(f"FAIL: Expected STARTED, got: {msg2.content}")
        bazel_proc.terminate()
        return 1
    print("PASS: Second test started (was queued and scheduled after first)")

    # Send CONTINUE to second test
    print("Sending CONTINUE to second test...")
    if not SocketServer.reply(msg2, "CONTINUE"):
        print("FAIL: Could not send CONTINUE to second test")
        bazel_proc.terminate()
        return 1

    # Wait for bazel to finish
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return 1

    print("\n=== All tests passed ===")
    print("Verified: Sequential scheduling works correctly with single worker")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-sequential-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_sequential_execution,
    )


if __name__ == "__main__":
    sys.exit(main())
