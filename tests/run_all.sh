#!/bin/bash
# Run all integration tests
# Each test uses a different set of ports so they can run simultaneously:
#   single_test:                    9000-9005  (9000-9004 services, 9005 socket)
#   single_failure_test:            9010-9014  (no socket server)
#   cache_hit:                      9020-9025  (9020-9024 services, 9025 socket)
#   deduplication:                  9030-9035  (9030-9034 services, 9035 socket)
#   1-worker-2-sequential:          9040-9045  (9040-9044 services, 9045 socket)
#   2-worker-2-parallel:            9050-9055  (9050-9054 services, 9055 socket)
#   platform-routing:               9060-9065  (9060-9064 services, 9065 socket)
#   no-workers-for-platform:        9070-9074  (no socket server)
#   multinode-count-validation:     9080-9084  (no socket server)
#   concurrency:                    9090-9095  (9090-9094 services, 9095 socket)
#   multinode-concurrency:          9100-9105  (9100-9104 services, 9105 socket)
#   multinode-scheduling:           9110-9115  (9110-9114 services, 9115 socket)
#   multinode-head-of-line-blocking: 9120-9125  (9120-9124 services, 9125 socket)
#   multinode-simultaneous:         9200-9205  (9200-9204 services, 9205 socket)

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
    //tests/multinode-scheduling:runner \
    //tests/multinode-head-of-line-blocking:runner \
    //tests/multinode-simultaneous:runner \
    --test_output=errors
