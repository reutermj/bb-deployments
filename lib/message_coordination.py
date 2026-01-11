"""Message coordination helpers for test runners.

Provides common patterns for coordinating with test binaries via socket messages:
- Collecting multiple STARTED messages
- Replying CONTINUE to collected messages
- Waiting for messages with timeout handling
"""

import subprocess
import time
from dataclasses import dataclass, field

from lib.socket_server import Message, SocketServer


@dataclass
class CollectedMessages:
    """Collection of messages received during a wait operation."""

    messages: list[Message] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.messages)

    def reply_all(self, response: str) -> bool:
        """Send a response to all collected connections.

        Args:
            response: The response string to send to all.

        Returns:
            True if all replies succeeded, False if any failed.
        """
        for msg in self.messages:
            if not SocketServer.reply(msg, response):
                return False
        return True

    def continue_all(self) -> bool:
        """Send CONTINUE to all collected connections.

        Returns:
            True if all replies succeeded, False if any failed.
        """
        return self.reply_all("CONTINUE")


def wait_for_started_messages(
    server: SocketServer,
    count: int,
    timeout: float = 60.0,
    expected_prefix: str = "STARTED",
) -> CollectedMessages | None:
    """Wait for multiple STARTED messages from test binaries.

    This is the most common coordination pattern: wait for N tests to send
    STARTED, then continue all of them.

    Args:
        server: The socket server to receive messages from.
        count: Number of STARTED messages to wait for.
        timeout: Maximum time to wait in seconds.
        expected_prefix: Message prefix to match (default: "STARTED").
                         Messages can be "STARTED" or "STARTED:<test_id>".

    Returns:
        CollectedMessages containing all received messages, or None on timeout/error.
        If messages are in "STARTED:<test_id>" format, test_ids will be populated.
    """
    collected = CollectedMessages()
    start_time = time.time()

    while len(collected) < count:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print(f"FAIL: Timeout waiting for {expected_prefix} messages")
            print(f"Only received {len(collected)} of {count} messages")
            return None

        msg = server.wait_for_message_with_conn(remaining)
        if msg is None:
            print(f"FAIL: Timeout waiting for {expected_prefix} message")
            return None

        # Check if message matches expected format
        if msg.content == expected_prefix:
            collected.messages.append(msg)
            collected.test_ids.append("")
            print(f"  Received {expected_prefix} ({len(collected)}/{count})")
        elif msg.content.startswith(f"{expected_prefix}:"):
            test_id = msg.content.split(":", 1)[1]
            collected.messages.append(msg)
            collected.test_ids.append(test_id)
            print(f"  Received {expected_prefix}:{test_id} ({len(collected)}/{count})")
        else:
            print(f"FAIL: Unexpected message: {msg.content}")
            return None

    return collected


def wait_for_test_group(
    server: SocketServer,
    test_id: str,
    count: int,
    timeout: float = 60.0,
) -> CollectedMessages | None:
    """Wait for all nodes of a specific test to send STARTED.

    Used for multinode tests where multiple workers execute parts of the same
    test and need to synchronize.

    Args:
        server: The socket server to receive messages from.
        test_id: The test ID to wait for (messages should be "STARTED:<test_id>").
        count: Number of nodes/messages to wait for.
        timeout: Maximum time to wait in seconds.

    Returns:
        CollectedMessages for the test, or None on timeout/error.
    """
    collected = CollectedMessages()
    start_time = time.time()

    while len(collected) < count:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print(f"FAIL: Timeout waiting for test {test_id}")
            print(f"Only received {len(collected)} of {count} nodes")
            return None

        msg = server.wait_for_message_with_conn(remaining)
        if msg is None:
            print(f"FAIL: Timeout waiting for message from test {test_id}")
            return None

        expected = f"STARTED:{test_id}"
        if msg.content == expected:
            collected.messages.append(msg)
            collected.test_ids.append(test_id)
            print(f"  Received {msg.content} ({len(collected)}/{count})")
        elif msg.content.startswith("STARTED:"):
            # Message from different test - log but still accept it
            # (caller can filter later if needed)
            actual_id = msg.content.split(":", 1)[1]
            collected.messages.append(msg)
            collected.test_ids.append(actual_id)
            print(f"  Received {msg.content} (expected {expected}, {len(collected)}/{count})")
        else:
            print(f"FAIL: Unexpected message format: {msg.content}")
            return None

    return collected


def expect_message(
    server: SocketServer,
    expected: str,
    timeout: float = 10.0,
) -> bool:
    """Wait for a specific message content.

    Simple validation that a specific message was received.

    Args:
        server: The socket server to receive messages from.
        expected: The exact message content to expect.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if the expected message was received, False otherwise.
    """
    message = server.wait_for_message(timeout)
    if message != expected:
        print(f"FAIL: Expected '{expected}', got: {message}")
        return False
    print(f"Received expected message: {expected}")
    return True


def expect_no_message(
    server: SocketServer,
    timeout: float = 3.0,
    description: str = "unexpected message",
) -> bool:
    """Verify no message is received within timeout.

    Used to confirm negative cases like:
    - No duplicate execution (deduplication test)
    - No misrouting to wrong worker (platform routing test)
    - Cache hit (no execution message)

    Args:
        server: The socket server to check for messages.
        timeout: Time to wait before confirming no message (seconds).
        description: Description of what was not expected (for error message).

    Returns:
        True if no message was received (success), False if a message was received.
    """
    msg = server.wait_for_message_with_conn(timeout)
    if msg is not None:
        print(f"FAIL: Got {description}: {msg.content}")
        return False
    print(f"PASS: No {description} received (timeout as expected)")
    return True


def run_and_collect_started(
    server: SocketServer,
    bazel_proc: subprocess.Popen,
    count: int,
    timeout: float = 60.0,
) -> CollectedMessages | None:
    """Collect STARTED messages from running bazel process.

    Convenience function that handles bazel process termination on failure.

    Args:
        server: The socket server to receive messages from.
        bazel_proc: The running bazel process (will be terminated on failure).
        count: Number of STARTED messages to collect.
        timeout: Maximum time to wait in seconds.

    Returns:
        CollectedMessages, or None on failure (bazel_proc will be terminated).
    """
    collected = wait_for_started_messages(server, count, timeout)
    if collected is None:
        bazel_proc.terminate()
        return None
    return collected
