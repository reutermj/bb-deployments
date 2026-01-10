"""Workspace utilities."""

import os

from python.runfiles import runfiles


def find_workspace_root() -> str:
    """Find the workspace root directory by locating MODULE.bazel."""
    # Use runfiles to find the workspace
    r = runfiles.Create()
    # Find MODULE.bazel in the workspace to determine root
    module_path = r.Rlocation("_main/MODULE.bazel")
    if module_path:
        return os.path.dirname(module_path)
    # Fallback: walk up from current file looking for MODULE.bazel
    current = os.path.dirname(os.path.abspath(__file__))
    while current != "/":
        if os.path.exists(os.path.join(current, "MODULE.bazel")):
            return current
        current = os.path.dirname(current)
    raise RuntimeError("Could not find workspace root")
