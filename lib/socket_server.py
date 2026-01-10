"""TCP socket server for receiving messages from test binaries."""

import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """A message received from a client, with the connection for replies."""

    content: str
    connection: socket.socket


class SocketServer:
    """TCP socket server that receives messages from test binaries.

    Uses TCP on localhost so that test binaries running on local workers
    can connect back to the test runner.

    Messages are newline-delimited strings. The server accepts multiple
    connections and collects all received messages.
    """

    def __init__(self, port: int = 0):
        """Create a socket server.

        Args:
            port: Port to listen on. Use 0 to let the OS assign a free port.
        """
        self._port = port
        self._actual_port: Optional[int] = None
        self._socket: Optional[socket.socket] = None
        self._messages: list[Message] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._accept_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def port(self) -> int:
        """Get the actual port the server is listening on."""
        if self._actual_port is None:
            raise RuntimeError("Server not started")
        return self._actual_port

    def start(self) -> None:
        """Start listening for connections."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", self._port))
        self._actual_port = self._socket.getsockname()[1]
        self._socket.listen(5)
        self._socket.settimeout(1.0)
        self._running = True

        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self) -> None:
        """Accept connections and spawn handler threads."""
        while self._running:
            try:
                conn, addr = self._socket.accept()
                handler = threading.Thread(
                    target=self._handle_connection, args=(conn,), daemon=True
                )
                handler.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single connection, receiving messages."""
        buffer = b""
        while self._running:
            try:
                conn.settimeout(1.0)
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    content = line.decode("utf-8").strip()
                    if content:
                        with self._condition:
                            self._messages.append(Message(content, conn))
                            self._condition.notify_all()
            except socket.timeout:
                continue
            except OSError:
                break

    def stop(self) -> None:
        """Stop the server and clean up."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._accept_thread:
            self._accept_thread.join(timeout=2.0)

    def wait_for_message(self, timeout: float) -> Optional[str]:
        """Wait for and return a single message content.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            The message string, or None if timeout expired.
        """
        msg = self.wait_for_message_with_conn(timeout)
        return msg.content if msg else None

    def wait_for_message_with_conn(self, timeout: float) -> Optional[Message]:
        """Wait for and return a message with its connection.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            The Message object (content + connection), or None if timeout expired.
        """
        deadline = time.time() + timeout
        with self._condition:
            while not self._messages:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
            return self._messages.pop(0)

    @staticmethod
    def reply(msg: Message, response: str) -> bool:
        """Send a response to a client.

        Args:
            msg: The message to reply to.
            response: The response string to send.

        Returns:
            True on success, False on failure.
        """
        try:
            msg.connection.sendall((response + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def __enter__(self) -> "SocketServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
