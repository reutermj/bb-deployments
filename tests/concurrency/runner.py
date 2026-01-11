"""Concurrent execution test runner.

This test validates that with a single worker (concurrency=8),
multiple tests can run simultaneously on the same worker.

The test schedules N jobs and verifies they ALL send STARTED before
any receives CONTINUE. This proves they are running concurrently.

Port allocation: 9090-9094
  - 9090: frontend (client-facing)
  - 9091: storage
  - 9092: scheduler (client gRPC)
  - 9093: scheduler (worker gRPC)
  - 9094: scheduler (admin HTTP)
  - 9884: socket server for test coordination
"""

import os
import shutil
import sys
import tempfile
import time

from lib.bazel_runner import run_bazel_test, shutdown_bazel
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

TEST_PORT = 9884
EXECUTOR_PORT = 9090
CONFIG_DIR = "_main/tests/concurrency/config"

# Services for concurrency test: single worker with concurrency=8
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker", f"{CONFIG_DIR}/worker.jsonnet", BINARY_WORKER),
    ServiceConfig("runner", f"{CONFIG_DIR}/runner.jsonnet", BINARY_RUNNER),
]


def test_concurrent_execution(
    workspace: str, output_base: str, server: SocketServer, num_jobs: int
) -> bool:
    """Test that N jobs run concurrently.

    Returns True if all jobs started concurrently, False otherwise.
    """
    print(f"\n=== Testing {num_jobs} concurrent jobs ===")
    print(f"Worker has concurrency=8, so all {num_jobs} tests should start simultaneously")

    # Start bazel tests (non-blocking)
    targets = [f"//tests/concurrency:test{i}" for i in range(1, num_jobs + 1)]
    bazel_proc = run_bazel_test(
        workspace,
        output_base,
        targets,
        EXECUTOR_PORT,
        extra_flags=["--nocache_test_results", f"--jobs={num_jobs}"],
    )

    # Collect all STARTED messages
    started_tests = []
    connections = []
    start_time = time.time()
    timeout = 60  # seconds

    print(f"\n--- Waiting for {num_jobs} tests to start ---")

    while len(started_tests) < num_jobs:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print("FAIL: Timeout waiting for all tests to start")
            print(f"Only received {len(started_tests)} of {num_jobs} STARTED messages")
            bazel_proc.terminate()
            return False

        msg = server.wait_for_message_with_conn(remaining)
        if msg is None:
            print("FAIL: Timeout waiting for STARTED message")
            bazel_proc.terminate()
            return False

        if msg.content.startswith("STARTED:"):
            test_id = msg.content.split(":")[1]
            started_tests.append(test_id)
            connections.append(msg)
            print(f"  Received STARTED from test{test_id} ({len(started_tests)}/{num_jobs})")
        else:
            print(f"FAIL: Unexpected message: {msg.content}")
            bazel_proc.terminate()
            return False

    print(f"\nAll {num_jobs} tests started - verified concurrent execution")

    # Now send CONTINUE to all tests
    print(f"\n--- Sending CONTINUE to all {num_jobs} tests ---")
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

    print(f"PASS: {num_jobs} tests ran concurrently")
    return True


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-concurrency-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(TEST_PORT) as server:
            print(f"Socket server listening on port {TEST_PORT}")

            services = ServiceManager(working_dir, SERVICES)

            if not services.start():
                print("FAIL: Could not start Buildbarn services")
                return 1

            try:
                print("\n=== Running concurrent execution tests ===")
                print("Testing that multiple jobs can run simultaneously on one worker")

                # Test with 2, 4, and 8 concurrent jobs
                for num_jobs in [2, 4, 8]:
                    if not test_concurrent_execution(
                        workspace, output_base, server, num_jobs
                    ):
                        return 1

            finally:
                services.stop()

        shutdown_bazel(workspace, output_base)

        print("\n=== All concurrency tests passed ===")
        print("Verified: Worker can execute multiple jobs concurrently")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
