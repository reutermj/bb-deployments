"""Remote execution test runner.

This test validates that a test binary executes remotely and sends
the expected message back to the runner.
"""

import os
import shutil
import subprocess
import sys
import tempfile

from lib.service_manager import ServiceManager
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9877

def run_bazel_test(workspace: str, output_base: str) -> bool:
    """Run bazel test with remote execution config."""
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--disk_cache=",
        "//tests/remote_execution:test",
    ]

    result = subprocess.run(cmd, cwd=workspace)
    return result.returncode == 0


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-remote-exec-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(TEST_PORT) as server:
            print(f"Socket server listening on port {TEST_PORT}")

            services = ServiceManager(working_dir)

            if not services.start():
                print("FAIL: Could not start Buildbarn services")
                return 1

            try:
                print("\n=== Running remote execution test ===")

                if not run_bazel_test(workspace, output_base):
                    print("FAIL: Bazel test failed")
                    return 1

                message = server.wait_for_message(10)
                if message != "EXECUTED":
                    print(f"FAIL: Expected EXECUTED message, got: {message}")
                    return 1

                print(f"PASS: Received expected message: {message}")

            finally:
                services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== Test passed ===")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
