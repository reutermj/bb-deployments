"""Test binary for deduplication test.

This binary:
1. Connects to the test runner
2. Sends a STARTED message
3. Waits for CONTINUE response
4. Exits successfully

The key for deduplication: this binary has NO environment variables or
other inputs that differ between test targets. Both test1 and test2
use the exact same binary with the same inputs, so they should be
deduplicated by the scheduler.
"""

import sys

from lib.test_client import TestClient

TEST_PORT = 9035


def main() -> int:
    client = TestClient("127.0.0.1", TEST_PORT)

    if not client.send("STARTED"):
        print(f"Failed to send STARTED message to port {TEST_PORT}")
        return 1

    print("Sent STARTED message, waiting for CONTINUE...")

    response = client.receive(60)
    if response != "CONTINUE":
        print(f"Expected CONTINUE, got: {response}")
        return 1

    print("Received CONTINUE, exiting")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
