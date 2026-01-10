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
