"""Single test runner.

This test validates that a test binary executes remotely and sends
the expected message back to the runner.
"""

import sys

from lib.bazel_runner import run_bazel_test_sync
from lib.service_manager import default_services
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9877
EXECUTOR_PORT = 9000
CONFIG_DIR = "_main/tests/single_test/config"


def test_single_execution(ctx: TestContextWithSocket) -> int:
    """Test that a single test executes remotely."""
    print("\n=== Running remote execution test ===")

    result = run_bazel_test_sync(
        ctx.workspace,
        ctx.output_base,
        ["//tests/single_test:test"],
        EXECUTOR_PORT,
    )
    if result.returncode != 0:
        print("FAIL: Bazel test failed")
        return 1

    message = ctx.server.wait_for_message(10)
    if message != "EXECUTED":
        print(f"FAIL: Expected EXECUTED message, got: {message}")
        return 1

    print(f"PASS: Received expected message: {message}")
    print("\n=== Test passed ===")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-single-",
        services=default_services(CONFIG_DIR),
        socket_port=TEST_PORT,
        test_fn=test_single_execution,
    )


if __name__ == "__main__":
    sys.exit(main())
