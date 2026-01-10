"""Test that the greeting was generated correctly."""

import os
import unittest
from pathlib import Path


def find_runfile(relative_path: str) -> Path:
    """Find a file in the runfiles directory."""
    # Try RUNFILES_DIR first
    runfiles_dir = os.environ.get("RUNFILES_DIR")
    if runfiles_dir:
        candidate = Path(runfiles_dir) / "com_github_buildbarn_bb_deployments" / relative_path
        if candidate.exists():
            return candidate

    # Try the manifest file approach
    manifest_file = os.environ.get("RUNFILES_MANIFEST_FILE")
    if manifest_file and Path(manifest_file).exists():
        with open(manifest_file) as f:
            for line in f:
                parts = line.strip().split(" ", 1)
                if len(parts) == 2 and parts[0].endswith(relative_path):
                    return Path(parts[1])

    # Fallback: look relative to the test script
    script_dir = Path(__file__).parent
    candidate = script_dir / Path(relative_path).name
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Could not find runfile: {relative_path}")


class GreetingTest(unittest.TestCase):
    def test_greeting_content(self):
        greeting_file = find_runfile("test_project/greeting.txt")
        content = greeting_file.read_text().strip()
        expected = "Hello from remote execution!"
        self.assertEqual(content, expected)


if __name__ == "__main__":
    unittest.main()
