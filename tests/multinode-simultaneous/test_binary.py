"""Test binary for multinode simultaneous scheduling test.

This binary:
1. Gets test ID from TEST_ID environment variable
2. Connects to the test runner
3. Sends a STARTED:<test_id> message
4. Waits for a CONTINUE response
5. Exits successfully
"""

import os
import sys

from lib.test_client import TestClient

TEST_PORT = 9205


def main() -> int:
    test_id = os.environ.get("TEST_ID", "unknown")
    client = TestClient("127.0.0.1", TEST_PORT)

    message = f"STARTED:{test_id}"
    if not client.send(message):
        print(f"Failed to send {message} to port {TEST_PORT}")
        return 1

    print(f"Sent {message}, waiting for CONTINUE...")

    response = client.receive(60)
    if response != "CONTINUE":
        print(f"Expected CONTINUE, got: {response}")
        return 1

    print("Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
