"""Test binary for scheduler chaos test.

This binary:
1. Connects to the test runner
2. Sends a STARTED message with its test ID
3. Waits for a CONTINUE response
4. Exits successfully

This allows the test runner to control when the action completes,
which is essential for testing scheduler kill during execution.
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9215


def main() -> int:
    # Get the test ID from the environment
    test_id = os.environ.get("TEST_ID", "unknown")

    client = TestClient("127.0.0.1", TEST_PORT)

    # Send STARTED message with test ID
    if not client.send(f"STARTED:{test_id}"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print(f"Test {test_id}: Sent STARTED message, waiting for CONTINUE...")

    # Wait for CONTINUE response (up to 120 seconds for chaos scenarios)
    response = client.receive(120)
    if response != "CONTINUE":
        print(f"Test {test_id}: Expected CONTINUE, got: {response}")
        return 1

    print(f"Test {test_id}: Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
