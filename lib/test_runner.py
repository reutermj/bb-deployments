"""Test runner framework for Buildbarn integration tests.

Provides common setup/teardown boilerplate for test runners including:
- Workspace discovery
- Temp directory creation and cleanup
- Service management lifecycle
- Optional socket server for test coordination
- Bazel shutdown
"""

import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from lib.bazel_runner import shutdown_bazel
from lib.service_manager import ServiceConfig, ServiceManager
from lib.workspace import find_workspace_root


@dataclass
class TestContext:
    """Context passed to test functions."""

    workspace: str
    working_dir: str
    output_base: str
    services: ServiceManager


@dataclass
class TestContextWithSocket:
    """Context passed to test functions that need a socket server."""

    workspace: str
    working_dir: str
    output_base: str
    services: ServiceManager
    server: "SocketServer"  # noqa: F821 - imported by caller


@contextmanager
def test_environment(
    temp_prefix: str,
    services: Sequence[ServiceConfig],
    extra_dirs: Sequence[str] | None = None,
) -> Iterator[TestContext]:
    """Context manager for test environment setup and teardown.

    Sets up:
    - Workspace root discovery
    - Temp directory with given prefix
    - Output base for bazel
    - ServiceManager with given services

    Tears down:
    - Stops all services
    - Shuts down bazel server
    - Cleans up temp directory

    Args:
        temp_prefix: Prefix for the temp directory name
        services: List of ServiceConfig for Buildbarn services
        extra_dirs: Optional extra directories to create in working_dir

    Yields:
        TestContext with workspace, working_dir, output_base, and services
    """
    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix=temp_prefix)
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        service_manager = ServiceManager(
            working_dir, list(services), list(extra_dirs) if extra_dirs else None
        )

        if not service_manager.start():
            print("FAIL: Could not start Buildbarn services")
            raise RuntimeError("Could not start Buildbarn services")

        try:
            yield TestContext(
                workspace=workspace,
                working_dir=working_dir,
                output_base=output_base,
                services=service_manager,
            )
        finally:
            service_manager.stop()

        shutdown_bazel(workspace, output_base)

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


@contextmanager
def test_environment_with_socket(
    temp_prefix: str,
    services: Sequence[ServiceConfig],
    socket_port: int,
    extra_dirs: Sequence[str] | None = None,
) -> Iterator[TestContextWithSocket]:
    """Context manager for test environment with socket server.

    Same as test_environment but also creates a SocketServer for
    test coordination.

    Args:
        temp_prefix: Prefix for the temp directory name
        services: List of ServiceConfig for Buildbarn services
        socket_port: Port for the socket server
        extra_dirs: Optional extra directories to create in working_dir

    Yields:
        TestContextWithSocket with workspace, working_dir, output_base, services, and server
    """
    # Import here to avoid circular dependency
    from lib.socket_server import SocketServer

    workspace = find_workspace_root()
    print(f"Workspace root: {workspace}")

    working_dir = tempfile.mkdtemp(prefix=temp_prefix)
    output_base = os.path.join(working_dir, "bazel-output")

    print(f"Working directory: {working_dir}")

    try:
        with SocketServer(socket_port) as server:
            print(f"Socket server listening on port {socket_port}")

            service_manager = ServiceManager(
                working_dir, list(services), list(extra_dirs) if extra_dirs else None
            )

            if not service_manager.start():
                print("FAIL: Could not start Buildbarn services")
                raise RuntimeError("Could not start Buildbarn services")

            try:
                yield TestContextWithSocket(
                    workspace=workspace,
                    working_dir=working_dir,
                    output_base=output_base,
                    services=service_manager,
                    server=server,
                )
            finally:
                service_manager.stop()

        shutdown_bazel(workspace, output_base)

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {working_dir}: {e}")


def run_test(
    temp_prefix: str,
    services: Sequence[ServiceConfig],
    test_fn: Callable[[TestContext], int],
    extra_dirs: Sequence[str] | None = None,
) -> int:
    """Run a test with automatic setup and teardown.

    This is a convenience wrapper around test_environment that handles
    the common pattern of running a single test function.

    Args:
        temp_prefix: Prefix for the temp directory name
        services: List of ServiceConfig for Buildbarn services
        test_fn: Function that receives TestContext and returns exit code
        extra_dirs: Optional extra directories to create in working_dir

    Returns:
        Exit code from test_fn, or 1 if setup failed
    """
    try:
        with test_environment(temp_prefix, services, extra_dirs) as ctx:
            return test_fn(ctx)
    except RuntimeError:
        return 1


def run_test_with_socket(
    temp_prefix: str,
    services: Sequence[ServiceConfig],
    socket_port: int,
    test_fn: Callable[[TestContextWithSocket], int],
    extra_dirs: Sequence[str] | None = None,
) -> int:
    """Run a test with socket server and automatic setup/teardown.

    This is a convenience wrapper around test_environment_with_socket that
    handles the common pattern of running a single test function.

    Args:
        temp_prefix: Prefix for the temp directory name
        services: List of ServiceConfig for Buildbarn services
        socket_port: Port for the socket server
        test_fn: Function that receives TestContextWithSocket and returns exit code
        extra_dirs: Optional extra directories to create in working_dir

    Returns:
        Exit code from test_fn, or 1 if setup failed
    """
    try:
        with test_environment_with_socket(
            temp_prefix, services, socket_port, extra_dirs
        ) as ctx:
            return test_fn(ctx)
    except RuntimeError:
        return 1
