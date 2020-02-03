# Copyright 2020 The gRPC Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import asyncio
import collections
import enum
import logging
import multiprocessing
import os
import time
import timeit
import yep

import grpc
from grpc.experimental import aio

from src.proto.grpc.testing import benchmark_service_pb2_grpc, messages_pb2

NUM_PROCESSOR = multiprocessing.cpu_count()
WorkloadResult = collections.namedtuple('WorkloadResult', ['qps', 'latencies'])


async def run_a_request(call, request, latencies):
    start = time.time()
    await call(request)
    latencies.append(time.time() - start)


async def run_requests(n, call, request, latencies):
    print('Running [%d] calls in a task' % n)
    for _ in range(n):
        start = time.time()
        await call(request)
        latencies.append(time.time() - start)


def connect(url):
    aio.init_grpc_aio()
    channel = aio.insecure_channel(url)
    stub = benchmark_service_pb2_grpc.BenchmarkServiceStub(channel)
    return stub.UnaryCall


async def workload(args):
    url, number, concurrency = args
    call = connect(url)
    request = messages_pb2.SimpleRequest(response_size=1)
    latencies = []

    if concurrency == 0:
        tasks = [run_a_request(call, request, latencies) for i in range(number)]
    else:
        tasks = []
        split = number // concurrency
        for _ in range(concurrency-1):
            tasks.append(run_requests(split, call, request, latencies))
        tasks.append(run_requests(number - split*(concurrency-1), call, request, latencies))

    start = time.time()
    await asyncio.gather(*tasks)
    time_elapsed = time.time() - start

    print('Running %d cycles of RPC calls in %f seconds QPS %f' %
          (number, time_elapsed, number / time_elapsed))

    return WorkloadResult(qps=len(latencies) / time_elapsed, latencies=latencies)


def print_latency(latencies):
    latencies.sort()
    print('Avg:\t%.7f ms' % (sum(latencies) / float(len(latencies))))
    print('L_50:\t%.7f ms' % (latencies[int(len(latencies) / 2)] * 1000))
    print('L_90:\t%.7f ms' %
          (latencies[int(len(latencies) / 100 * 90)] * 1000))
    print('L_99:\t%.7f ms' %
          (latencies[int(len(latencies) / 100 * 99)] * 1000))


async def single(url, n, c):
    print('Benchmark against [%s] total [%d] concurrency [%d]' % (url, n, c))
    return await workload((url, n, c))


async def cprofile(work):
    import cProfile, pstats, io
    from pstats import SortKey
    pr = cProfile.Profile()

    pr.enable()
    result = await work
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.TIME)
    ps.print_stats()
    return result, s.getvalue()


async def yeprofile(work):
    print('Starting Yep profiling...')
    yep.start('/tmp/aio.prof')
    result = await work
    yep.stop()
    print('Stopped Yep profiling.')
    return result


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, nargs='?',
                        default='localhost:50051')
    parser.add_argument('-c', type=int, nargs='?', default=0)
    parser.add_argument('-n', type=int, nargs='?', default=100)
    parser.add_argument('-p', action='store_true')
    return parser.parse_args()


async def main():
    args = parse_arguments()
    print('Value of P', args.p)

    printable = None
    if not args.p:
        result = await single(args.url, args.n, args.c)
    else:
        result = await yeprofile(single(args.url, args.n, args.c))
        # result, printable = await cprofile(single(args.url, args.n))
    print_latency(result.latencies)
    print('Total QPS is %.2f' % result.qps)
    if printable is not None:
        print(printable)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())


