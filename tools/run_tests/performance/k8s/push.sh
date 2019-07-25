#! /bin/bash -ex

docker tag qps-driver gcr.io/grpc-testing/benchmark_qps_driver
docker push gcr.io/grpc-testing/benchmark_qps_driver
docker tag cpp-worker gcr.io/grpc-testing/benchmark_cpp_worker
docker push gcr.io/grpc-testing/benchmark_cpp_worker
