"""Test binary for platform routing test.

This binary:
1. Connects to the test runner
2. Sends a STARTED:<TEST_ID> message identifying which test it is
3. Waits for a CONTINUE response
4. Exits successfully

The TEST_ID environment variable identifies this test instance.
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9065


def main() -> int:
    test_id = os.environ.get("TEST_ID", "unknown")

    client = TestClient("127.0.0.1", TEST_PORT)

    # Send STARTED message with test ID
    if not client.send(f"STARTED:{test_id}"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print(f"[{test_id}] Sent STARTED message, waiting for CONTINUE...")

    # Wait for CONTINUE response (up to 60 seconds - longer for routing test)
    response = client.receive(60)
    if response != "CONTINUE":
        print(f"[{test_id}] Expected CONTINUE, got: {response}")
        return 1

    print(f"[{test_id}] Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
