"""Test binary for multinode scheduling test.

This binary:
1. Connects to the test runner
2. Sends a STARTED message with TEST_ID
3. Waits for a CONTINUE response
4. Exits successfully

The TEST_ID environment variable identifies which 2-node test this belongs to.
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9115


def main() -> int:
    test_id = os.environ.get("TEST_ID", "unknown")

    client = TestClient("127.0.0.1", TEST_PORT)

    if not client.send(f"STARTED:{test_id}"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print(f"Sent STARTED:{test_id}, waiting for CONTINUE...")

    response = client.receive(60)
    if response != "CONTINUE":
        print(f"Expected CONTINUE, got: {response}")
        return 1

    print("Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
