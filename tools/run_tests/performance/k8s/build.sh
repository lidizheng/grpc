#! /bin/bash -ex

mkdir -p tools/dockerfile/benchmark/cpp_builder/build
docker build -t cpp-builder tools/dockerfile/benchmark/cpp_builder
docker run --rm \
    --volume=`pwd`:/var/local/src/grpc:ro \
    --volume=`pwd`/tools/dockerfile/benchmark/cpp_builder/build:/var/local/output \
    cpp-builder

ln -Fs `pwd`/tools/dockerfile/benchmark/cpp_builder/build tools/dockerfile/benchmark/qps_driver/build
docker build -t qps-driver tools/dockerfile/benchmark/qps_driver

ln -Fs `pwd`/tools/dockerfile/benchmark/cpp_builder/build tools/dockerfile/benchmark/cpp_worker/build
docker build -t cpp-worker tools/dockerfile/benchmark/cpp_worker
