"""Single test runner.

This test validates that a test binary executes remotely and sends
the expected message back to the runner.
"""

import os
import shutil
import sys
import tempfile

from lib.bazel_runner import run_bazel_test_sync, shutdown_bazel
from lib.service_manager import ServiceManager, default_services
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9877
EXECUTOR_PORT = 9000
CONFIG_DIR = "_main/tests/single_test/config"


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-single-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(TEST_PORT) as server:
            print(f"Socket server listening on port {TEST_PORT}")

            services = ServiceManager(working_dir, default_services(CONFIG_DIR))

            if not services.start():
                print("FAIL: Could not start Buildbarn services")
                return 1

            try:
                print("\n=== Running remote execution test ===")

                result = run_bazel_test_sync(
                    workspace,
                    output_base,
                    ["//tests/single_test:test"],
                    EXECUTOR_PORT,
                )
                if result.returncode != 0:
                    print("FAIL: Bazel test failed")
                    return 1

                message = server.wait_for_message(10)
                if message != "EXECUTED":
                    print(f"FAIL: Expected EXECUTED message, got: {message}")
                    return 1

                print(f"PASS: Received expected message: {message}")

            finally:
                services.stop()

        shutdown_bazel(workspace, output_base)

        print("\n=== Test passed ===")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
