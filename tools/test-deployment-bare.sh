#!/usr/bin/env bash
# Verifies that the bare deployment works.

set -eux -o pipefail -E

rm -rf tmp-test-bare

script_dir=$(dirname "${BASH_SOURCE[0]}")
root="$(realpath "$script_dir"/..)"
cd "$root"

test_output_base="test_output_base"
bare_output="bb-output.txt"

working_directory="$root"/tmp-test-bare
mkdir "$working_directory"
cd "$working_directory"

data=bb-data
mkdir "$data"

# Determine platform-specific parameters.
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    # Prevent // being converted to /.
    export MSYS_NO_PATHCONV=1
    script_name="run_bare.cmd"
    script_exec="cmd.exe /c $script_name"
    data="$(pwd -W)/$data"
    kill_sig='SIGINT'
    remote_exec_config='--config=remote-local --config=remote-exec-windows'
    export OS="Windows"
else
    script_name="run_bare.sh"
    script_exec="./$script_name"
    data="$PWD/$data"
    kill_sig='TERM'
    remote_exec_config='--config=remote-local'
    export OS=$(uname)
fi

bazel run --script_path="$script_name" -- //bare "$data"
$script_exec </dev/null 2>"${bare_output}" &
buildbarn_pid=$!

# Wait for buildbarn to start.
sleep 5

cleanup() {
    EXIT_STATUS=$?
    kill "$buildbarn_pid" || true
    wait "$buildbarn_pid" || true
    if [ "$EXIT_STATUS" -ne "0" ]; then
        cat "$bare_output" || true
    fi
    bazel --output_base="$test_output_base" shutdown
    # Some Python toolchain files have restrictive permissions; fix before removing.
    chmod -R u+w "$data" "$test_output_base" "$working_directory" 2>/dev/null || true
    rm -rf "$data" "$test_output_base" "$working_directory"
    exit "$EXIT_STATUS"
}
trap cleanup EXIT

# --- Run remote execution ---
bazel --output_base="$test_output_base" clean
bazel --output_base="$test_output_base" \
    test --color=no --curses=no $remote_exec_config --disk_cache= \
    //test_project:all_tests
# Make sure there are remote executions but no cache hits.
# INFO: 8 processes: 2 internal, 6 remote.
grep -E '^INFO: [0-9]+ processes: .*[0-9]+ remote[.,]' \
    "$test_output_base/command.log" \
    | grep -v 'remote cache hit'

# --- Check that we get cache hit even after rebooting the server ---
kill -s $kill_sig "$buildbarn_pid"
wait "$buildbarn_pid" || true
$script_exec 2>"${bare_output}" &
buildbarn_pid=$!
sleep 5

bazel --output_base="$test_output_base" clean
bazel --output_base="$test_output_base"  \
    test --color=no --curses=no $remote_exec_config --disk_cache= \
    //test_project:all_tests
# Make sure there are remote cache hits but no remote executions.
# INFO: 8 processes: 6 remote cache hit, 2 internal.
grep -E '^INFO: [0-9]+ processes: .*[0-9]+ remote cache hit[.,]' \
    "$test_output_base/command.log" \
    | grep -v 'remote[,.]'
