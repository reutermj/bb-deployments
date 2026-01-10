"""Buildbarn bare deployment launcher.

This script starts all Buildbarn services (storage, frontend, scheduler, worker,
runner) and manages their lifecycle, including graceful shutdown on SIGTERM.
"""

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from python.runfiles import runfiles


@dataclass
class BuildbarnProcess:
    config: str
    binary: str


BUILDBARN_PROCESSES = [
    BuildbarnProcess(
        config="_main/bare/config/storage.jsonnet",
        binary="com_github_buildbarn_bb_storage+/cmd/bb_storage/bb_storage_/bb_storage",
    ),
    BuildbarnProcess(
        config="_main/bare/config/frontend.jsonnet",
        binary="com_github_buildbarn_bb_storage+/cmd/bb_storage/bb_storage_/bb_storage",
    ),
    BuildbarnProcess(
        config="_main/bare/config/scheduler.jsonnet",
        binary="com_github_buildbarn_bb_remote_execution+/cmd/bb_scheduler/bb_scheduler_/bb_scheduler",
    ),
    BuildbarnProcess(
        config="_main/bare/config/worker.jsonnet",
        binary="com_github_buildbarn_bb_remote_execution+/cmd/bb_worker/bb_worker_/bb_worker",
    ),
    BuildbarnProcess(
        config="_main/bare/config/runner.jsonnet",
        binary="com_github_buildbarn_bb_remote_execution+/cmd/bb_runner/bb_runner_/bb_runner",
    ),
]

SIGTERM_TIMEOUT = 60  # seconds


class BuildbarnLauncher:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.runfiles = runfiles.Create()
        self.processes: list[tuple[BuildbarnProcess, subprocess.Popen]] = []
        self.shutdown_requested = False
        self.kill_requested = False

    def _resolve_path(self, path: str) -> Optional[str]:
        """Resolve a runfiles path to an absolute path."""
        resolved = self.runfiles.Rlocation(path)
        if resolved is None:
            print(f"Couldn't find {path}", file=sys.stderr)
        return resolved

    def _create_directories(self) -> None:
        """Create required directories for Buildbarn."""
        dirs = [
            "storage-ac",
            "storage-ac/persistent_state",
            "storage-cas",
            "storage-cas/persistent_state",
            "worker",
            "worker/build",
            "worker/cache",
        ]
        for d in dirs:
            path = Path(self.working_dir) / d if self.working_dir else Path(d)
            path.mkdir(parents=True, exist_ok=True)

    def _start_process(self, bb_process: BuildbarnProcess) -> Optional[subprocess.Popen]:
        """Start a single Buildbarn process."""
        binary = bb_process.binary
        if sys.platform == "win32":
            binary += ".exe"

        binary_path = self._resolve_path(binary)
        if binary_path is None:
            return None

        config_path = self._resolve_path(bb_process.config)
        if config_path is None:
            return None

        env = os.environ.copy()
        # PWD is used by the jsonnet configs to find data directories.
        # On Windows it's not set by default, and on Linux it may be stale
        # when running via bazel run --script_path.
        env["PWD"] = self.working_dir or os.getcwd()

        try:
            proc = subprocess.Popen(
                [binary_path, config_path],
                stdout=sys.stdout,
                stderr=sys.stderr,
                cwd=self.working_dir or None,
                env=env,
            )
            return proc
        except OSError as e:
            print(f"Failed starting {bb_process.binary}: {e}", file=sys.stderr)
            return None

    def _graceful_shutdown(self, proc: subprocess.Popen) -> None:
        """Send graceful shutdown signal to a process."""
        if sys.platform == "win32":
            # On Windows, CTRL_C_EVENT is sent to the whole process group.
            pass
        else:
            try:
                proc.send_signal(signal.SIGTERM)
            except OSError:
                pass  # Process may have already exited

    def _handle_sigterm(self, signum: int, frame) -> None:
        """Handle first SIGTERM - request graceful shutdown."""
        if not self.shutdown_requested:
            print("Received SIGTERM, gracefully terminating Buildbarn processes")
            self.shutdown_requested = True
        else:
            print("Received second SIGTERM, killing Buildbarn processes")
            self.kill_requested = True

    def _wait_for_processes(self) -> bool:
        """Wait for all processes and handle shutdown.

        Returns True if all processes exited successfully.
        """
        # Wait for any process to exit or shutdown signal
        while not self.shutdown_requested:
            for bb_process, proc in self.processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"Exit code {ret} from {bb_process.binary} with PID {proc.pid}")
                    self.shutdown_requested = True
                    break
            if not self.shutdown_requested:
                time.sleep(0.1)

        # Send SIGTERM to all processes
        for bb_process, proc in self.processes:
            if proc.poll() is None:
                self._graceful_shutdown(proc)

        # Wait for graceful shutdown or timeout
        deadline = time.time() + SIGTERM_TIMEOUT
        while time.time() < deadline and not self.kill_requested:
            all_exited = all(proc.poll() is not None for _, proc in self.processes)
            if all_exited:
                break
            time.sleep(0.1)

        # Kill any remaining processes
        if not all(proc.poll() is not None for _, proc in self.processes):
            print("SIGTERM handling was slow, killing Buildbarn processes")
            for bb_process, proc in self.processes:
                if proc.poll() is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass

        # Wait for all to finish
        for bb_process, proc in self.processes:
            proc.wait()
            print(f"Exit code {proc.returncode} from {bb_process.binary} with PID {proc.pid}")

        return all(proc.returncode == 0 for _, proc in self.processes)

    def run(self) -> int:
        """Run the Buildbarn deployment.

        Returns exit code (0 for success, 1 for failure).
        """
        self._create_directories()

        print("Don't worry if you see some \"Failed to synchronize with scheduler\" warnings on startup")
        print("\t- they should stop once bb_scheduler is ready")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        # Start all processes
        for bb_process in BUILDBARN_PROCESSES:
            proc = self._start_process(bb_process)
            if proc is None:
                self.shutdown_requested = True
                break
            print(f"Started {bb_process.binary} with PID {proc.pid}")
            self.processes.append((bb_process, proc))

        if not self.processes:
            return 1

        success = self._wait_for_processes()
        return 0 if success else 1


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: bare [absolute-working-directory]", file=sys.stderr)
        return 1

    working_dir = ""
    if len(sys.argv) == 2:
        working_dir = sys.argv[1]
        if not os.path.isabs(working_dir):
            print(f"{working_dir} must be absolute", file=sys.stderr)
            return 1
        if not os.path.exists(working_dir):
            print(f"{working_dir} does not exist", file=sys.stderr)
            return 1

    launcher = BuildbarnLauncher(working_dir)
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())
