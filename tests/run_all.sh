#!/bin/bash
# Run all tests in parallel
# Each test uses a different set of ports so they can run simultaneously:
#   single_test:                    9000-9004
#   single_failure_test:            9010-9014
#   cache_hit:                      9020-9024
#   deduplication:                  9030-9034
#   1-worker-2-sequential:          9040-9044
#   2-worker-2-parallel:            9050-9054
#   platform-routing:               9060-9064
#   no-workers-for-platform:        9070-9074
#   multinode-count-validation:     9080-9084
#   concurrency:                    9090-9094
#   multinode-concurrency:          9100-9104

set -e

TESTS=(
    "//tests/single_test:runner"
    "//tests/single_failure_test:runner"
    "//tests/cache_hit:runner"
    "//tests/deduplication:runner"
    "//tests/1-worker-2-sequential:runner"
    "//tests/2-worker-2-parallel:runner"
    "//tests/platform-routing:runner"
    "//tests/no-workers-for-platform:runner"
    "//tests/multinode-count-validation:runner"
    "//tests/concurrency:runner"
    "//tests/multinode-concurrency:runner"
)

echo "Running ${#TESTS[@]} tests in parallel..."
echo

# Create temp directory for logs
LOG_DIR=$(mktemp -d)
echo "Logs will be in: $LOG_DIR"
echo

# Start all tests in background
PIDS=()
for test in "${TESTS[@]}"; do
    # Extract test name for log file
    test_name=$(echo "$test" | sed 's|//tests/||' | sed 's|:runner||')
    log_file="$LOG_DIR/$test_name.log"

    echo "Starting: $test"
    bazel run "$test" > "$log_file" 2>&1 &
    PIDS+=($!)
done

echo
echo "All tests started. Waiting for completion..."
echo

# Wait for all tests and collect results
FAILED=()
for i in "${!TESTS[@]}"; do
    test="${TESTS[$i]}"
    pid="${PIDS[$i]}"
    test_name=$(echo "$test" | sed 's|//tests/||' | sed 's|:runner||')
    log_file="$LOG_DIR/$test_name.log"

    if wait "$pid"; then
        echo "PASS: $test_name"
    else
        echo "FAIL: $test_name"
        FAILED+=("$test_name")
    fi
done

echo
echo "========================================"
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "All ${#TESTS[@]} tests passed!"
    rm -rf "$LOG_DIR"
    exit 0
else
    echo "FAILED tests (${#FAILED[@]}/${#TESTS[@]}):"
    for test in "${FAILED[@]}"; do
        echo "  - $test"
        echo "    Log: $LOG_DIR/$test.log"
    done
    echo
    echo "Logs preserved in: $LOG_DIR"
    exit 1
fi
