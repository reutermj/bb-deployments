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

TEST_PORT = 9885
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


def run_bazel_test(
    workspace: str, output_base: str, multinode_count: int
) -> subprocess.Popen:
    """Start bazel test with remote execution config.

    Runs a single test target with multinode_count=N.
    Returns the Popen object (non-blocking).
    """
    target = f"//tests/multinode-concurrency:test_multinode_{multinode_count}"

    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--remote_executor=grpc://localhost:9100",
        "--disk_cache=",
        "--nocache_test_results",
        target,
    ]

    return subprocess.Popen(cmd, cwd=workspace)


def test_multinode_concurrent_execution(
    workspace: str, output_base: str, server: SocketServer, multinode_count: int
) -> bool:
    """Test that a multinode job with N tasks runs N tasks concurrently.

    Returns True if all N tasks started concurrently, False otherwise.
    """
    print(f"\n=== Testing multinode_count={multinode_count} ===")
    print(
        f"With 8 workers (concurrency=1 each), all {multinode_count} tasks should start simultaneously"
    )

    # Start bazel test (non-blocking)
    bazel_proc = run_bazel_test(workspace, output_base, multinode_count)

    # Collect all STARTED messages
    started_count = 0
    connections = []
    start_time = time.time()
    timeout = 60  # seconds

    print(f"\n--- Waiting for {multinode_count} tasks to start ---")

    while started_count < multinode_count:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print("FAIL: Timeout waiting for all tasks to start")
            print(
                f"Only received {started_count} of {multinode_count} STARTED messages"
            )
            bazel_proc.terminate()
            return False

        msg = server.wait_for_message_with_conn(remaining)
        if msg is None:
            print("FAIL: Timeout waiting for STARTED message")
            bazel_proc.terminate()
            return False

        if msg.content == "STARTED":
            started_count += 1
            connections.append(msg)
            print(f"  Received STARTED ({started_count}/{multinode_count})")
        else:
            print(f"FAIL: Unexpected message: {msg.content}")
            bazel_proc.terminate()
            return False

    print(f"\nAll {multinode_count} tasks started - verified concurrent execution")

    # Now send CONTINUE to all tasks
    print(f"\n--- Sending CONTINUE to all {multinode_count} tasks ---")
    for msg in connections:
        if not SocketServer.reply(msg, "CONTINUE"):
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


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-multinode-concurrency-")
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
                print("\n=== Running multinode concurrency tests ===")
                print(
                    "Testing that multinode jobs run tasks concurrently on different workers"
                )

                # Test with 2, 4, and 8 multinode tasks
                for multinode_count in [2, 4, 8]:
                    if not test_multinode_concurrent_execution(
                        workspace, output_base, server, multinode_count
                    ):
                        return 1

            finally:
                services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== All multinode concurrency tests passed ===")
        print("Verified: Multinode jobs run tasks concurrently on different workers")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
