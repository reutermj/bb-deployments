#!/bin/bash
# Run all tests one at a time

set -e

TESTS=(
    "//tests/single_test:runner"
    "//tests/single_failure_test:runner"
    "//tests/cache_hit:runner"
    "//tests/1-worker-2-sequential:runner"
    "//tests/2-worker-2-parallel:runner"
    "//tests/platform-routing:runner"
)

echo "Running ${#TESTS[@]} tests..."
echo

for test in "${TESTS[@]}"; do
    echo "========================================"
    echo "Running: $test"
    echo "========================================"
    bazel run "$test"
    echo
done

echo "========================================"
echo "All tests passed!"
echo "========================================"
