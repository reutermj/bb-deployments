"""Test binary that runs on Buildbarn workers.

This binary connects to the test runner via TCP socket and sends
an "EXECUTED" message to indicate it was actually executed (not cached).
"""

import sys

from lib.test_client import TestClient

TEST_PORT = 9025

def main() -> int:
    client = TestClient("127.0.0.1", TEST_PORT)
    if client.send("EXECUTED"):
        print(f"Sent EXECUTED message to test runner on port {TEST_PORT}")
    else:
        print(f"Failed to send message to test runner on port {TEST_PORT}")
    client.close()

    # The test itself is trivial - we just care about whether it executes
    print("Test binary executed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
