#! /bin/bash -ex

mkdir -p tools/dockerfile/benchmark/cpp_worker/build
docker build -t cpp-builder tools/dockerfile/benchmark/cpp_worker
docker run --rm \
    --volume=`pwd`:/var/local/src/grpc:ro \
    --volume=`pwd`/tools/dockerfile/benchmark/cpp_worker/build:/var/local/output \
    cpp-builder

cp tools/dockerfile/benchmark/cpp_worker/build tools/dockerfile/benchmark/qps_driver/build
docker build -t qps-driver tools/dockerfile/benchmark/qps_driver
