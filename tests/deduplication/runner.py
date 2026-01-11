"""Deduplication test runner.

This test validates that the scheduler deduplicates identical actions.

Setup:
- 2 separate bazel clients requesting the SAME test target simultaneously
- Both use different output bases but request the same action

Expected behavior:
- Only 1 STARTED message received (action executes once)
- Both bazel clients succeed (both receive the same result)

This validates the in-flight deduplication described in ARCHITECTURE.md:
when two clients request the same action, the scheduler only executes
it once and returns the same result to both.

Note: This test uses 2 output bases, which doesn't fit the standard
test_runner pattern, so it uses a custom main() function.
"""

import os
import shutil
import sys
import tempfile

from lib.bazel_runner import run_bazel_test, shutdown_bazel_servers
from lib.message_coordination import expect_no_message, wait_for_started_messages
from lib.service_manager import ServiceManager, default_services
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9880
EXECUTOR_PORT = 9030
CONFIG_DIR = "_main/tests/deduplication/config"


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-dedup-")
    output_base1 = os.path.join(working_dir, "bazel-output1")
    output_base2 = os.path.join(working_dir, "bazel-output2")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(TEST_PORT) as server:
            print(f"Socket server listening on port {TEST_PORT}")

            services = ServiceManager(working_dir, default_services(CONFIG_DIR))

            if not services.start():
                print("FAIL: Could not start Buildbarn services")
                return 1

            try:
                print("\n=== Running deduplication test ===")
                print("Launching 2 bazel clients for the SAME test target...")
                print("Expected: Only 1 execution (deduplicated)")

                # Start both bazel clients for the same test
                bazel_proc1 = run_bazel_test(
                    workspace,
                    output_base1,
                    ["//tests/deduplication:test1"],
                    EXECUTOR_PORT,
                )
                bazel_proc2 = run_bazel_test(
                    workspace,
                    output_base2,
                    ["//tests/deduplication:test1"],
                    EXECUTOR_PORT,
                )

                # Wait for first STARTED message
                print("\n--- Waiting for STARTED message ---")
                collected = wait_for_started_messages(server, count=1, timeout=60)
                if collected is None:
                    bazel_proc1.terminate()
                    bazel_proc2.terminate()
                    return 1

                print("Received first STARTED message")

                # Wait briefly to see if a second STARTED arrives (it shouldn't)
                print("\n--- Checking for duplicate execution (should timeout) ---")
                if not expect_no_message(
                    server, timeout=3, description="second STARTED (deduplication failed)"
                ):
                    bazel_proc1.terminate()
                    bazel_proc2.terminate()
                    return 1

                print("PASS: No second execution (deduplication working)")

                # Continue the single execution
                print("\n--- Continuing the deduplicated execution ---")
                if not collected.continue_all():
                    print("FAIL: Could not send CONTINUE")
                    bazel_proc1.terminate()
                    bazel_proc2.terminate()
                    return 1

                # Wait for both bazel clients to finish
                print("Waiting for both bazel clients to complete...")
                bazel_proc1.wait()
                bazel_proc2.wait()

                if bazel_proc1.returncode != 0:
                    print(f"FAIL: Bazel client 1 failed with code {bazel_proc1.returncode}")
                    return 1

                if bazel_proc2.returncode != 0:
                    print(f"FAIL: Bazel client 2 failed with code {bazel_proc2.returncode}")
                    return 1

                print("PASS: Both bazel clients succeeded with single execution")

            finally:
                services.stop()

        # Shutdown both bazel servers
        shutdown_bazel_servers(workspace, [output_base1, output_base2])

        print("\n=== Test passed ===")
        print("Verified: In-flight deduplication works correctly")
        print("- Identical actions execute only once")
        print("- Both clients receive the same result")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
