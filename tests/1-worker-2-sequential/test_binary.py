"""Test binary for sequential execution test.

This binary:
1. Connects to the test runner
2. Sends a STARTED message
3. Waits for a CONTINUE response
4. Exits successfully
"""

import sys

from lib.test_client import TestClient

TEST_PORT = 9045


def main() -> int:
    client = TestClient("127.0.0.1", TEST_PORT)

    # Send STARTED message
    if not client.send("STARTED"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print("Sent STARTED message, waiting for CONTINUE...")

    # Wait for CONTINUE response (up to 30 seconds)
    response = client.receive(30)
    if response != "CONTINUE":
        print(f"Expected CONTINUE, got: {response}")
        return 1

    print("Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
