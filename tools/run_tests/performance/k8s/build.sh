#! /bin/bash -ex

mkdir -p tools/dockerfile/benchmark/cpp_worker/build
docker build -t cpp-builder tools/dockerfile/benchmark/cpp_worker
docker run --rm -d \
    --volume=`pwd`:/var/local/git/grpc:ro \
    --volume=`pwd`/tools/dockerfile/benchmark/cpp_worker/build:/var/local/output \
    cpp-builder
