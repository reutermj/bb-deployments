"""Test binary for multinode_count validation tests.

For rejection tests (exceeds max, zero, negative, non-integer):
  This binary should never execute - the scheduler should reject the action.
  If this binary runs, the test has failed.

For valid tests (multinode_count=1 or 4):
  Sends an "EXECUTED" message to confirm remote execution occurred.
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9878


def main() -> int:
    # Check if we're a rejection test based on environment
    # Rejection tests have multinode_count that should be rejected by scheduler
    multinode_count = os.environ.get("MULTINODE_COUNT_TEST_VALUE")

    if multinode_count in ("100", "0", "-1", "invalid"):
        # This should never execute - scheduler should reject first
        print("ERROR: This binary should never execute!")
        print("The scheduler should have rejected the action due to invalid multinode_count.")
        return 1

    # Valid multinode_count - send confirmation to test runner
    client = TestClient("127.0.0.1", TEST_PORT)
    if client.send("EXECUTED"):
        print(f"Sent EXECUTED message to test runner on port {TEST_PORT}")
    else:
        print(f"Failed to send message to test runner on port {TEST_PORT}")
    client.close()

    print("Test binary executed successfully with valid multinode_count")
    return 0


if __name__ == "__main__":
    sys.exit(main())
