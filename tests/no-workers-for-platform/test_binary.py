"""Test binary for no-workers-for-platform test.

This binary should never execute - the scheduler should reject the action
because no workers exist for the requested platform.

If this binary runs, the test has failed.
"""

import sys


def main() -> int:
    print("ERROR: This binary should never execute!")
    print("The scheduler should have rejected the action due to no matching workers.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
