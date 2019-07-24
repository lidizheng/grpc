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

python tools/run_tests/performance/k8s/gen_scenario.py > scenario.json

docker run --rm --name the-qps-driver \
    --volume `pwd`/scenario.json:/var/local/scenario.json:ro \
    --volume `pwd`:/var/local/result
    --network host \
    --env=QPS_WORKERS="localhost:10001,localhost:10002" \
    qps-driver \
    --scenarios_file=/var/local/scenario.json \
    --scenario_result_file=/var/local/result/benchmark_result.json
