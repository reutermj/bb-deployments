"""Test binary for multinode head-of-line blocking test - notify only variant.

This binary:
1. Connects to the test runner
2. Sends a STARTED message with TEST_ID
3. Exits immediately (no wait for CONTINUE)

Used for the multinode job that just needs to notify it started,
without blocking for acknowledgment.
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9125


def main() -> int:
    test_id = os.environ.get("TEST_ID", "unknown")

    client = TestClient("127.0.0.1", TEST_PORT)

    if not client.send(f"STARTED:{test_id}"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print(f"Sent STARTED:{test_id}, exiting immediately")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
