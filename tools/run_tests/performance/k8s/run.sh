#! /bin/bash -ex

docker run --rm --name cpp-worker-1 \
    -d --network host \
    cpp-worker --driver_port=10001
docker run --rm --name cpp-worker-2 \
    -d --network host \
    cpp-worker --driver_port=10002

docker run --rm --name the-qps-driver \
    --network host --env="QPS_WORKERS='localhost:10001;localhost:10002'" qps-driver
