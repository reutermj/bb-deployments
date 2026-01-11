"""Test failure detection runner.

This test validates that bazel correctly detects when a test
binary fails (exits with non-zero status).

Test flow:
1. Start services
2. Run bazel test
3. Verify bazel test returns non-zero (failure detected)
"""

import os
import shutil
import subprocess
import sys
import tempfile

from lib.service_manager import ServiceManager, default_services
from lib.workspace import find_workspace_root

CONFIG_DIR = "_main/tests/single_failure_test/config"


def run_bazel_test(workspace: str, output_base: str) -> int:
    """Run bazel test with remote execution config.

    Returns the exit code.
    """
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        "--disk_cache=",
        "//tests/single_failure_test:test",
    ]

    result = subprocess.run(cmd, cwd=workspace)
    return result.returncode


def main() -> int:
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix="bb-test-failure-")
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        services = ServiceManager(working_dir, default_services(CONFIG_DIR))

        if not services.start():
            print("FAIL: Could not start Buildbarn services")
            return 1

        try:
            print("\n=== Running test failure detection test ===")

            exit_code = run_bazel_test(workspace, output_base)

            if exit_code == 0:
                print("FAIL: Bazel test should have failed but returned 0")
                return 1

            print(f"PASS: Bazel test correctly failed with code {exit_code}")

        finally:
            services.stop()

        subprocess.run(
            ["bazel", f"--output_base={output_base}", "shutdown"],
            cwd=workspace,
            check=False,
        )

        print("\n=== Test passed ===")
        print("Verified: Test runner correctly detects test failure")
        return 0

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
