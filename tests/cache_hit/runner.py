"""Cache hit test runner.

This test validates that:
1. First run: test binary executes remotely (receives EXECUTED message)
2. Second run: test binary is cached (no EXECUTED message)

Note: This test has unique service restart logic that doesn't fit the
standard test_runner pattern, so it uses a custom main() function.
"""

import os
import shutil
import subprocess
import sys
import tempfile

from lib.bazel_runner import run_bazel_test_sync, shutdown_bazel
from lib.message_coordination import expect_message, expect_no_message
from lib.service_manager import ServiceManager, default_services
from lib.socket_server import SocketServer
from lib.workspace import find_workspace_root

TEST_PORT = 9876
EXECUTOR_PORT = 9020
CONFIG_DIR = "_main/tests/cache_hit/config"


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

                result = run_bazel_test_sync(
                    workspace,
                    output_base,
                    ["//tests/cache_hit:test"],
                    EXECUTOR_PORT,
                )
                if result.returncode != 0:
                    print("FAIL: Bazel test failed on first run")
                    return 1

                if not expect_message(server, "EXECUTED", timeout=10):
                    return 1

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
                result = run_bazel_test_sync(
                    workspace,
                    output_base,
                    ["//tests/cache_hit:test"],
                    EXECUTOR_PORT,
                )
                if result.returncode != 0:
                    print("FAIL: Bazel test failed on second run")
                    return 1

                # Short timeout since we expect no message (cache hit)
                if not expect_no_message(server, timeout=5, description="execution message"):
                    return 1

            finally:
                services.stop()

        shutdown_bazel(workspace, output_base)

        print("\n=== All tests passed ===")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
