#!/bin/bash
# Run all integration tests
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

bazel test \
    //tests/single_test:runner \
    //tests/single_failure_test:runner \
    //tests/cache_hit:runner \
    //tests/deduplication:runner \
    //tests/1-worker-2-sequential:runner \
    //tests/2-worker-2-parallel:runner \
    //tests/platform-routing:runner \
    //tests/no-workers-for-platform:runner \
    //tests/multinode-count-validation:runner \
    //tests/concurrency:runner \
    //tests/multinode-concurrency:runner \
    --test_output=errors
