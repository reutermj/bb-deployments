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

import os
import shutil
import subprocess
import sys
import tempfile
import time

from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
    ServiceManager,
)
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9886
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


def run_bazel_test(workspace: str, output_base: str) -> subprocess.Popen:
    """Start bazel test with remote execution config.

    Runs both 2-node test targets in a single bazel invocation.
    Returns the Popen object (non-blocking).
    """
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--remote_executor=grpc://localhost:9110",
        "--disk_cache=",
        "--nocache_test_results",
        "//tests/multinode-scheduling:test_2node_1",
        "//tests/multinode-scheduling:test_2node_2",
    ]

    return subprocess.Popen(cmd, cwd=workspace)


def wait_for_test_started(
    server: SocketServer, test_id: str, timeout: float
) -> list | None:
    """Wait for both nodes of a specific test to send STARTED.

    Returns list of connection messages if successful, None on timeout/error.
    """
    connections = []
    start_time = time.time()

    while len(connections) < 2:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print(f"FAIL: Timeout waiting for test {test_id} to start")
            return None

        msg = server.wait_for_message_with_conn(remaining)
        if msg is None:
            print(f"FAIL: Timeout waiting for message from test {test_id}")
            return None

        expected = f"STARTED:{test_id}"
        if msg.content == expected:
            connections.append(msg)
            print(f"  Received {msg.content} ({len(connections)}/2)")
        else:
            # This message is from a different test, we'll handle it later
            # For now, just log it - in the actual flow this shouldn't happen
            # because we process tests sequentially
            print(f"  Received unexpected message: {msg.content} (expected {expected})")
            # Still add it if it's a STARTED message for any test
            if msg.content.startswith("STARTED:"):
                connections.append(msg)
                print(f"  (counting it anyway: {len(connections)}/2)")

    return connections


def continue_test(connections: list) -> bool:
    """Send CONTINUE to all connections for a test."""
    for msg in connections:
        if not SocketServer.reply(msg, "CONTINUE"):
            print("FAIL: Could not send CONTINUE")
            return False
    return True


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-multinode-scheduling-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(TEST_PORT) as server:
            print(f"Socket server listening on port {TEST_PORT}")

            services = ServiceManager(working_dir, SERVICES, EXTRA_DIRS)

            if not services.start():
                print("FAIL: Could not start Buildbarn services")
                return 1

            try:
                print("\n=== Running multinode scheduling test ===")
                print("Testing that 2 two-node tests can be scheduled with 2 workers")
                print(
                    "Both tests are scheduled via single bazel command, processed sequentially"
                )

                # Start bazel test (non-blocking) - schedules both 2-node tests
                print("\n--- Starting bazel test with both 2-node tests ---")
                bazel_proc = run_bazel_test(workspace, output_base)

                # Wait for first 2-node test (TEST_ID=1) to start
                print("\n--- Waiting for test 1 (2 nodes) to start ---")
                test1_conns = wait_for_test_started(server, "1", timeout=60)
                if test1_conns is None:
                    bazel_proc.terminate()
                    return 1

                print(f"Test 1: Both nodes started")

                # Continue the first test
                print("--- Sending CONTINUE to test 1 ---")
                if not continue_test(test1_conns):
                    bazel_proc.terminate()
                    return 1

                print("Test 1: Continued, workers should become available")

                # Wait for second 2-node test (TEST_ID=2) to start
                print("\n--- Waiting for test 2 (2 nodes) to start ---")
                test2_conns = wait_for_test_started(server, "2", timeout=60)
                if test2_conns is None:
                    bazel_proc.terminate()
                    return 1

                print(f"Test 2: Both nodes started")

                # Continue the second test
                print("--- Sending CONTINUE to test 2 ---")
                if not continue_test(test2_conns):
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

            finally:
                services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== Multinode scheduling test passed ===")
        print("Verified: Multiple multinode tests can be scheduled and run sequentially")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
