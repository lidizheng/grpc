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
"""Stress test for gRPC AsyncIO stack."""

import asyncio
import logging
import time
import random
import unittest
import threading

import grpc
from grpc.experimental import aio

from src.proto.grpc.testing import empty_pb2, messages_pb2, test_pb2_grpc
from tests_aio.unit._test_server import start_test_server

NO_REUSE_PORT = (('grpc.so_reuseport', 0),)


def create_client_thread(target: str, stop_event: threading.Event):
    channel = grpc.insecure_channel(target)
    stub = test_pb2_grpc.TestServiceStub(channel)

    def workload():
        while not stop_event.is_set():
            stub.UnaryCall(messages_pb2.SimpleRequest())

    thread = threading.Thread(target=workload, daemon=True)
    thread.start()
    return thread


def create_async_client_thread(target: str, stop_event: threading.Event):

    def workload():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        channel = aio.insecure_channel(target)
        stub = test_pb2_grpc.TestServiceStub(channel)

        async def body():
            while not stop_event.is_set():
                await stub.UnaryCall(messages_pb2.SimpleRequest())

        loop.run_until_complete(body())

    thread = threading.Thread(target=workload, daemon=True)
    thread.start()
    return thread


def create_async_server_thread(stop_event: threading.Event):
    return_value = []
    server_started = threading.Event()

    def workload():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def body():
            address, server = await start_test_server()
            return_value.append(address)
            server_started.set()
            while not stop_event.is_set():
                await asyncio.sleep(1)

        loop.run_until_complete(body())

    thread = threading.Thread(target=workload, daemon=True)
    thread.start()
    return thread, return_value[0]


class StressTest(unittest.TestCase):

    def test_stressful_load(self):
        stop_event = threading.Event()

        server_thread, address = create_async_server_thread(stop_event)
        client_thread_1 = create_client_thread(address, stop_event)
        client_thread_2 = create_async_client_thread(address, stop_event)

        time.sleep(10)
        stop_event.set()

        client_thread_1.join()
        client_thread_2.join()
        server_thread.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(verbosity=2)
