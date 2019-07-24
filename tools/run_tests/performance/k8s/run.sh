#! /bin/bash -ex

docker kill cpp-worker-1
docker kill cpp-worker-2
docker run --rm --name cpp-worker-1 \
    -d --network host \
    --env=GRPC_VERBOSITY=debug \
    cpp-worker --driver_port=10001
docker run --rm --name cpp-worker-2 \
    -d --network host \
    --env=GRPC_VERBOSITY=debug \
    cpp-worker --driver_port=10002

SCENARIO_JSON=$(python tools/run_tests/performance/k8s/gen_scenario.py)

docker run --rm --name the-qps-driver \
    --volume `pwd`/s.json:/var/local/scenario.json \
    --network host \
    --env=QPS_WORKERS="localhost:10001,localhost:10002" \
    qps-driver --scenarios_file=/var/local/scenario.json
