#! /bin/bash -ex

cp -r /var/local/src/grpc /var/local/work
cd /var/local/work/grpc && ./tools/run_tests/performance/build_performance.sh

cp /var/local/work/grpc/cmake/build/qps_json_driver /var/local/output
cp /var/local/work/grpc/cmake/build/qps_worker /var/local/output
