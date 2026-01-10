"""Buildbarn service manager for test framework."""

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
class ServiceConfig:
    """Configuration for a Buildbarn service."""

    name: str
    config: str  # Full runfiles path to config, e.g., "_main/tests/foo/config/storage.jsonnet"
    binary: str


# Binary paths for each service type
BINARY_STORAGE = "com_github_buildbarn_bb_storage+/cmd/bb_storage/bb_storage_/bb_storage"
BINARY_SCHEDULER = "com_github_buildbarn_bb_remote_execution+/cmd/bb_scheduler/bb_scheduler_/bb_scheduler"
BINARY_WORKER = "com_github_buildbarn_bb_remote_execution+/cmd/bb_worker/bb_worker_/bb_worker"
BINARY_RUNNER = "com_github_buildbarn_bb_remote_execution+/cmd/bb_runner/bb_runner_/bb_runner"


def default_services(config_dir: str) -> list[ServiceConfig]:
    """Create the default service list for a given config directory."""
    return [
        ServiceConfig("storage", f"{config_dir}/storage.jsonnet", BINARY_STORAGE),
        ServiceConfig("frontend", f"{config_dir}/frontend.jsonnet", BINARY_STORAGE),
        ServiceConfig("scheduler", f"{config_dir}/scheduler.jsonnet", BINARY_SCHEDULER),
        ServiceConfig("worker", f"{config_dir}/worker.jsonnet", BINARY_WORKER),
        ServiceConfig("runner", f"{config_dir}/runner.jsonnet", BINARY_RUNNER),
    ]

REQUIRED_DIRS = [
    "storage-ac",
    "storage-ac/persistent_state",
    "storage-cas",
    "storage-cas/persistent_state",
    "worker",
    "worker/build",
    "worker/cache",
]

SIGTERM_TIMEOUT = 30
STARTUP_WAIT = 5


class ServiceManager:
    """Manages Buildbarn service lifecycle for testing."""

    def __init__(
        self,
        working_dir: str,
        services: list[ServiceConfig],
    ):
        self.working_dir = working_dir
        self.services = services
        self._runfiles = runfiles.Create()
        self._processes: list[tuple[ServiceConfig, subprocess.Popen]] = []

    def _resolve_path(self, path: str) -> Optional[str]:
        """Resolve a runfiles path to an absolute path."""
        resolved = self._runfiles.Rlocation(path)
        if resolved is None:
            print(f"Couldn't find {path}", file=sys.stderr)
        return resolved

    def _create_directories(self) -> None:
        """Create required directories for Buildbarn."""
        for d in REQUIRED_DIRS:
            path = Path(self.working_dir) / d
            path.mkdir(parents=True, exist_ok=True)

    def _start_service(self, service: ServiceConfig) -> Optional[subprocess.Popen]:
        """Start a single Buildbarn service."""
        binary = service.binary
        if sys.platform == "win32":
            binary += ".exe"

        binary_path = self._resolve_path(binary)
        if binary_path is None:
            return None

        config_path = self._resolve_path(service.config)
        if config_path is None:
            return None

        env = os.environ.copy()
        env["PWD"] = self.working_dir

        try:
            proc = subprocess.Popen(
                [binary_path, config_path],
                stdout=sys.stdout,
                stderr=sys.stderr,
                cwd=self.working_dir,
                env=env,
            )
            return proc
        except OSError as e:
            print(f"Failed starting {service.name}: {e}", file=sys.stderr)
            return None

    def start(self) -> bool:
        """Start all Buildbarn services.

        Returns True if all services started successfully.
        """
        self._create_directories()

        print("Starting Buildbarn services...")
        print(
            "Note: 'Failed to synchronize with scheduler' warnings are expected during startup"
        )

        for service in self.services:
            proc = self._start_service(service)
            if proc is None:
                self.stop()
                return False
            print(f"Started {service.name} with PID {proc.pid}")
            self._processes.append((service, proc))

        print(f"Waiting {STARTUP_WAIT}s for services to initialize...")
        time.sleep(STARTUP_WAIT)
        return True

    def stop(self) -> None:
        """Stop all Buildbarn services."""
        if not self._processes:
            return

        print("Stopping Buildbarn services...")

        # Send SIGTERM to all processes
        for service, proc in self._processes:
            if proc.poll() is None:
                try:
                    proc.send_signal(signal.SIGTERM)
                except OSError:
                    pass

        # Wait for graceful shutdown
        deadline = time.time() + SIGTERM_TIMEOUT
        while time.time() < deadline:
            if all(proc.poll() is not None for _, proc in self._processes):
                break
            time.sleep(0.1)

        # Kill any remaining processes
        for service, proc in self._processes:
            if proc.poll() is None:
                print(f"Killing {service.name} (PID {proc.pid})")
                try:
                    proc.kill()
                except OSError:
                    pass

        # Wait for all to finish
        for service, proc in self._processes:
            proc.wait()
            print(f"{service.name} exited with code {proc.returncode}")

        self._processes.clear()

    def restart(self) -> bool:
        """Restart all services (preserves data directories).

        Returns True if all services restarted successfully.
        """
        self.stop()
        # Don't recreate directories - preserve cache data
        print("Restarting Buildbarn services...")

        for service in self.services:
            proc = self._start_service(service)
            if proc is None:
                self.stop()
                return False
            print(f"Started {service.name} with PID {proc.pid}")
            self._processes.append((service, proc))

        print(f"Waiting {STARTUP_WAIT}s for services to initialize...")
        time.sleep(STARTUP_WAIT)
        return True

    def is_running(self) -> bool:
        """Check if all services are still running."""
        return all(proc.poll() is None for _, proc in self._processes)

    def __enter__(self) -> "ServiceManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
