"""Cache hit test runner.

This test validates that:
1. First run: test binary executes remotely (receives EXECUTED message)
2. Second run: test binary is cached (no EXECUTED message)
"""

import os
import shutil
import subprocess
import sys
import tempfile

from lib.service_manager import ServiceManager, default_services
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9876
CONFIG_DIR = "_main/tests/cache_hit/config"

def run_bazel_test(workspace: str, output_base: str) -> bool:
    """Run bazel test with remote execution config.

    Returns True if bazel test succeeded.
    """
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--disk_cache=",
        "//tests/cache_hit:test",
    ]

    result = subprocess.run(cmd, cwd=workspace)
    return result.returncode == 0


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-cache-hit-")
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
                # === Phase 1: First run - expect execution ===
                print("\n=== Phase 1: First run (expect remote execution) ===")

                if not run_bazel_test(workspace, output_base):
                    print("FAIL: Bazel test failed on first run")
                    return 1

                message = server.wait_for_message(10)
                if message != "EXECUTED":
                    print(f"FAIL: Expected EXECUTED message, got: {message}")
                    return 1

                print(f"PASS: Received expected message: {message}")

                # === Phase 2: Restart services and expect cache hit ===
                print("\n=== Phase 2: Second run (expect cache hit) ===")

                subprocess.run(
                    ["bazel", f"--output_base={output_base}", "clean"],
                    cwd=workspace,
                    check=True,
                )

                if not services.restart():
                    print("FAIL: Could not restart Buildbarn services")
                    return 1

                # Run the test synchronously, then check for messages after.
                # On a cache hit, bazel returns success but no message is sent.
                if not run_bazel_test(workspace, output_base):
                    print("FAIL: Bazel test failed on second run")
                    return 1

                # Short timeout since we expect no message (cache hit)
                message = server.wait_for_message(5)
                if message is not None:
                    print(f"FAIL: Expected no message (cache hit), got: {message}")
                    return 1

                print("PASS: No message received (cache hit)")

            finally:
                services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== All tests passed ===")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
