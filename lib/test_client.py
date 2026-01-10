"""Client library for test binaries to communicate with the test runner."""

import socket
from typing import Optional


class TestClient:
    """Client for sending messages to the test runner via TCP socket."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._socket: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Connect to the socket server.

        Returns True on success, False on failure.
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))
            return True
        except OSError:
            self._socket = None
            return False

    def send(self, message: str) -> bool:
        """Send a message to the server.

        Automatically connects if not already connected.
        Returns True on success, False on failure.
        """
        if self._socket is None:
            if not self.connect():
                return False
        try:
            self._socket.sendall((message + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def receive(self, timeout: float) -> Optional[str]:
        """Wait for and receive a message from the server.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            The message string, or None if timeout expired or error.
        """
        if self._socket is None:
            return None
        try:
            self._socket.settimeout(timeout)
            buffer = b""
            while b"\n" not in buffer:
                data = self._socket.recv(4096)
                if not data:
                    return None
                buffer += data
            line, _ = buffer.split(b"\n", 1)
            return line.decode("utf-8").strip()
        except (OSError, socket.timeout):
            return None

    def close(self) -> None:
        """Close the connection."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def __enter__(self) -> "TestClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
