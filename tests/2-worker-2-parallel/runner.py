"""Parallel execution test runner.

This test validates that:
1. Two test binaries can execute simultaneously on separate workers
2. Both binaries connect and send STARTED messages
3. Runner waits for both, then sends CONTINUE to both
4. Both binaries complete and send DONE messages
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
from lib.socket_server import Message, SocketServer
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9882
EXECUTOR_PORT = 9050
CONFIG_DIR = "_main/tests/2-worker-2-parallel/config"

# Services for parallel test: 2 worker/runner pairs
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker1", f"{CONFIG_DIR}/worker1.jsonnet", BINARY_WORKER),
    ServiceConfig("runner1", f"{CONFIG_DIR}/runner1.jsonnet", BINARY_RUNNER),
    ServiceConfig("worker2", f"{CONFIG_DIR}/worker2.jsonnet", BINARY_WORKER),
    ServiceConfig("runner2", f"{CONFIG_DIR}/runner2.jsonnet", BINARY_RUNNER),
]

# Extra directories for the two workers
EXTRA_DIRS = [
    "worker1",
    "worker1/build",
    "worker1/cache",
    "worker2",
    "worker2/build",
    "worker2/cache",
]


def test_parallel_execution(ctx: TestContextWithSocket) -> int:
    """Test that tests run in parallel on separate workers."""
    print("\n=== Running parallel execution test ===")

    # Start bazel tests (non-blocking)
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [
            "//tests/2-worker-2-parallel:test1",
            "//tests/2-worker-2-parallel:test2",
        ],
        EXECUTOR_PORT,
        extra_flags=["--jobs=2"],
    )

    # Wait for both STARTED messages
    print("Waiting for STARTED messages from both workers...")
    started_messages: list[Message] = []

    for i in range(2):
        msg = ctx.server.wait_for_message_with_conn(60)
        if msg is None:
            print(f"FAIL: Timeout waiting for STARTED message {i+1}")
            bazel_proc.terminate()
            return 1
        if msg.content != "STARTED":
            print(f"FAIL: Expected STARTED, got: {msg.content}")
            bazel_proc.terminate()
            return 1
        print(f"Received STARTED message {i+1}")
        started_messages.append(msg)

    print("PASS: Both workers started")

    # Send CONTINUE to both workers
    print("Sending CONTINUE to both workers...")
    for i, msg in enumerate(started_messages):
        if not SocketServer.reply(msg, "CONTINUE"):
            print(f"FAIL: Could not send CONTINUE to worker {i+1}")
            bazel_proc.terminate()
            return 1

    # Wait for both DONE messages
    print("Waiting for DONE messages from both workers...")
    for i in range(2):
        msg = ctx.server.wait_for_message(60)
        if msg != "DONE":
            print(f"FAIL: Expected DONE, got: {msg}")
            bazel_proc.terminate()
            return 1
        print(f"Received DONE message {i+1}")

    print("PASS: Both workers completed")

    # Wait for bazel to finish
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return 1

    print("\n=== All tests passed ===")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-parallel-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_parallel_execution,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
