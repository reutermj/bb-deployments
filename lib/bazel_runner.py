"""Bazel test invocation helpers for the test framework."""

import subprocess
from typing import Sequence


def run_bazel_test(
    workspace: str,
    output_base: str,
    targets: Sequence[str],
    executor_port: int,
    extra_flags: Sequence[str] | None = None,
) -> subprocess.Popen:
    """Start bazel test with remote execution config (non-blocking).

    Args:
        workspace: Path to the workspace root
        output_base: Path to the bazel output base
        targets: Test targets to run
        executor_port: Port of the remote executor (frontend)
        extra_flags: Additional bazel flags (e.g., --jobs=2, --nocache_test_results)

    Returns:
        Popen object for the running bazel process
    """
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        f"--remote_executor=grpc://localhost:{executor_port}",
        "--disk_cache=",
    ]

    if extra_flags:
        cmd.extend(extra_flags)

    cmd.extend(targets)

    return subprocess.Popen(cmd, cwd=workspace)


def run_bazel_test_sync(
    workspace: str,
    output_base: str,
    targets: Sequence[str],
    executor_port: int,
    extra_flags: Sequence[str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run bazel test with remote execution config (blocking).

    Args:
        workspace: Path to the workspace root
        output_base: Path to the bazel output base
        targets: Test targets to run
        executor_port: Port of the remote executor (frontend)
        extra_flags: Additional bazel flags
        capture_output: If True, capture stdout/stderr

    Returns:
        CompletedProcess with return code (and optionally stdout/stderr)
    """
    cmd = [
        "bazel",
        f"--output_base={output_base}",
        "test",
        "--config=remote-local",
        f"--remote_executor=grpc://localhost:{executor_port}",
        "--disk_cache=",
    ]

    if extra_flags:
        cmd.extend(extra_flags)

    cmd.extend(targets)

    if capture_output:
        return subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
    else:
        return subprocess.run(cmd, cwd=workspace)


def shutdown_bazel(workspace: str, output_base: str) -> None:
    """Shutdown the bazel server for the given output base."""
    subprocess.run(
        ["bazel", f"--output_base={output_base}", "shutdown"],
        cwd=workspace,
        check=False,
    )


def shutdown_bazel_servers(workspace: str, output_bases: Sequence[str]) -> None:
    """Shutdown multiple bazel servers."""
    for output_base in output_bases:
        shutdown_bazel(workspace, output_base)
