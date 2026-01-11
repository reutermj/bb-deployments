"""Platform routing test runner.

This test validates that the scheduler correctly routes actions to workers
based on platform properties.

Setup:
- 2 workers: one with arch=arch1, one with arch=arch2
- 3 tests: test_arch1_a and test_arch1_b target arch1, test_arch2 targets arch2

Test flow:
1. Launch all 3 tests simultaneously
2. Expect one test on each arch to start (arch1 worker gets one of arch1 tests,
   arch2 worker gets the arch2 test)
3. Continue only the arch2 test - it completes
4. Wait briefly to confirm the second arch1 test does NOT get misrouted to arch2
5. Continue the first arch1 test - it completes
6. Wait for the second arch1 test to start on arch1 worker
7. Continue it - test passes

This validates:
- Platform-based routing works correctly
- Tests are not misrouted to wrong architecture
- Queue handles multiple tests for same platform correctly
"""

import sys

from lib.bazel_runner import run_bazel_test
from lib.service_manager import (
    BINARY_RUNNER,
    BINARY_SCHEDULER,
    BINARY_STORAGE,
    BINARY_WORKER,
    ServiceConfig,
)
from lib.socket_server import Message, SocketServer
from lib.test_runner import TestContextWithSocket, run_test_with_socket

TEST_PORT = 9883
EXECUTOR_PORT = 9060
CONFIG_DIR = "_main/tests/platform-routing/config"

# Services: 2 workers with different platforms
SERVICES = [
    ServiceConfig("storage", f"{CONFIG_DIR}/storage.jsonnet", BINARY_STORAGE),
    ServiceConfig("frontend", f"{CONFIG_DIR}/frontend.jsonnet", BINARY_STORAGE),
    ServiceConfig("scheduler", f"{CONFIG_DIR}/scheduler.jsonnet", BINARY_SCHEDULER),
    ServiceConfig("worker-arch1", f"{CONFIG_DIR}/worker-arch1.jsonnet", BINARY_WORKER),
    ServiceConfig("runner-arch1", f"{CONFIG_DIR}/runner-arch1.jsonnet", BINARY_RUNNER),
    ServiceConfig("worker-arch2", f"{CONFIG_DIR}/worker-arch2.jsonnet", BINARY_WORKER),
    ServiceConfig("runner-arch2", f"{CONFIG_DIR}/runner-arch2.jsonnet", BINARY_RUNNER),
]

EXTRA_DIRS = [
    "worker-arch1",
    "worker-arch1/build",
    "worker-arch1/cache",
    "worker-arch2",
    "worker-arch2/build",
    "worker-arch2/cache",
]


def test_platform_routing(ctx: TestContextWithSocket) -> int:
    """Test platform-based routing."""
    print("\n=== Running platform routing test ===")
    print("arch1 worker handles: test_arch1_a, test_arch1_b")
    print("arch2 worker handles: test_arch2")

    # Start all tests
    bazel_proc = run_bazel_test(
        ctx.workspace,
        ctx.output_base,
        [
            "//tests/platform-routing:test_arch1_a",
            "//tests/platform-routing:test_arch1_b",
            "//tests/platform-routing:test_arch2",
        ],
        EXECUTOR_PORT,
        extra_flags=["--jobs=3"],
    )

    # === Phase 1: Wait for initial scheduling ===
    # We expect 2 tests to start: one on arch1, one on arch2
    print("\n--- Phase 1: Waiting for initial tests to start ---")
    print("Expecting one test on each arch...")

    first_messages: dict[str, Message] = {}  # test_id -> Message

    # Wait for 2 STARTED messages (one per arch)
    for i in range(2):
        msg = ctx.server.wait_for_message_with_conn(60)
        if msg is None:
            print(f"FAIL: Timeout waiting for STARTED message {i+1}")
            bazel_proc.terminate()
            return 1

        if not msg.content.startswith("STARTED:"):
            print(f"FAIL: Expected STARTED:<id>, got: {msg.content}")
            bazel_proc.terminate()
            return 1

        test_id = msg.content.split(":", 1)[1]
        print(f"Received STARTED from {test_id}")
        first_messages[test_id] = msg

    # Validate we got one from each platform type
    arch1_tests = [t for t in first_messages if t.startswith("arch1")]
    arch2_tests = [t for t in first_messages if t.startswith("arch2")]

    if len(arch2_tests) != 1:
        print(f"FAIL: Expected exactly 1 arch2 test, got: {arch2_tests}")
        bazel_proc.terminate()
        return 1

    if len(arch1_tests) != 1:
        print(f"FAIL: Expected exactly 1 arch1 test initially, got: {arch1_tests}")
        bazel_proc.terminate()
        return 1

    print(f"PASS: Got one test per arch - arch1: {arch1_tests[0]}, arch2: {arch2_tests[0]}")
    first_arch1_test = arch1_tests[0]
    arch2_test = arch2_tests[0]

    # === Phase 2: Continue arch2 test only ===
    print("\n--- Phase 2: Continue arch2 test, leave arch1 blocked ---")
    print(f"Continuing {arch2_test}...")

    if not SocketServer.reply(first_messages[arch2_test], "CONTINUE"):
        print(f"FAIL: Could not send CONTINUE to {arch2_test}")
        bazel_proc.terminate()
        return 1

    # === Phase 3: Verify arch2 doesn't pick up arch1 work ===
    print("\n--- Phase 3: Verify no misrouting ---")
    print("Waiting 5s to confirm arch2 worker doesn't pick up arch1 work...")

    # Wait briefly - if arch1's second test gets misrouted, it would start now
    misrouted_msg = ctx.server.wait_for_message_with_conn(5)
    if misrouted_msg is not None:
        print(f"FAIL: Got unexpected message (possible misrouting): {misrouted_msg.content}")
        bazel_proc.terminate()
        return 1

    print("PASS: No misrouting detected (timeout as expected)")

    # === Phase 4: Continue first arch1 test ===
    print("\n--- Phase 4: Continue first arch1 test ---")
    print(f"Continuing {first_arch1_test}...")

    if not SocketServer.reply(first_messages[first_arch1_test], "CONTINUE"):
        print(f"FAIL: Could not send CONTINUE to {first_arch1_test}")
        bazel_proc.terminate()
        return 1

    # === Phase 5: Wait for second arch1 test ===
    print("\n--- Phase 5: Wait for second arch1 test ---")
    print("The queued arch1 test should now start on arch1 worker...")

    msg = ctx.server.wait_for_message_with_conn(60)
    if msg is None:
        print("FAIL: Timeout waiting for second arch1 test")
        bazel_proc.terminate()
        return 1

    if not msg.content.startswith("STARTED:"):
        print(f"FAIL: Expected STARTED:<id>, got: {msg.content}")
        bazel_proc.terminate()
        return 1

    second_arch1_test = msg.content.split(":", 1)[1]
    print(f"Received STARTED from {second_arch1_test}")

    if not second_arch1_test.startswith("arch1"):
        print(f"FAIL: Expected arch1 test, got: {second_arch1_test}")
        bazel_proc.terminate()
        return 1

    if second_arch1_test == first_arch1_test:
        print(f"FAIL: Got same test twice: {second_arch1_test}")
        bazel_proc.terminate()
        return 1

    print(f"PASS: Second arch1 test started: {second_arch1_test}")

    # === Phase 6: Continue second arch1 test ===
    print("\n--- Phase 6: Continue second arch1 test ---")
    print(f"Continuing {second_arch1_test}...")

    if not SocketServer.reply(msg, "CONTINUE"):
        print(f"FAIL: Could not send CONTINUE to {second_arch1_test}")
        bazel_proc.terminate()
        return 1

    # Wait for bazel to finish
    bazel_proc.wait()
    if bazel_proc.returncode != 0:
        print(f"FAIL: Bazel test failed with code {bazel_proc.returncode}")
        return 1

    print("\n=== All tests passed ===")
    print("Verified: Platform routing works correctly")
    print("- Tests are routed to correct architecture")
    print("- Tests are not misrouted when workers are idle")
    print("- Queue handles multiple tests for same platform")
    return 0


def main() -> int:
    return run_test_with_socket(
        temp_prefix="bb-test-platform-",
        services=SERVICES,
        socket_port=TEST_PORT,
        test_fn=test_platform_routing,
        extra_dirs=EXTRA_DIRS,
    )


if __name__ == "__main__":
    sys.exit(main())
