"""Test binary that fails.

Simply exits with non-zero status to simulate a test failure.
"""

import sys


def main() -> int:
    print("Test binary executing, now failing...")
    return 1


if __name__ == "__main__":
    sys.exit(main())
