#! /bin/bash -ex

cp -r /var/local/src/grpc /var/local/work
cd /var/local/work/grpc && ./tools/run_tests/performance/build_performance.sh

cp /var/local/work/grpc/cmake/build/* /var/local/output
