# Copyright 2019 The gRPC Authors.
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

import asyncio
import logging
import os
import unittest

from concurrent import futures
import grpc

from grpc.experimental import aio
from tests_aio.unit import test_base
from src.proto.grpc.testing import messages_pb2


def _grpc_blocking_call(target):
    with grpc.insecure_channel(target) as channel:
        hi = channel.unary_unary(
            '/grpc.testing.TestService/UnaryCall',
            request_serializer=messages_pb2.SimpleRequest.SerializeToString,
            response_deserializer=messages_pb2.SimpleResponse.FromString)
        hi(messages_pb2.SimpleRequest())
        return True


def _grpc_aio_call(target):

    async def coro():
        aio.init_grpc_aio()
        async with aio.insecure_channel(target) as channel:
            hi = channel.unary_unary(
                '/grpc.testing.TestService/UnaryCall',
                request_serializer=messages_pb2.SimpleRequest.SerializeToString,
                response_deserializer=messages_pb2.SimpleResponse.FromString)
            await hi(messages_pb2.SimpleRequest())
            return True

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro())


async def _run_in_another_process(function, target):
    loop = asyncio.get_event_loop()
    with futures.ProcessPoolExecutor() as pool:
        return await loop.run_in_executor(pool, function, target)


class TestInitGrpcAio(test_base.AioTestBase):
    # We double check that once the Aio is initialized a fork syscall can
    # be executed and the child process can use the both versions of
    # the gRPC library.
    @unittest.skipIf(os.name == 'nt', 'fork not supported on windows')
    def test_aio_supports_fork_and_grpc_blocking_usable(self):
        successful_call = self.loop.run_until_complete(
            _run_in_another_process(_grpc_blocking_call, self.server_target))
        self.assertEqual(successful_call, True)

    @unittest.skipIf(os.name == 'nt', 'fork not supported on windows')
    def test_aio_supports_fork_and_grpc_aio_usable(self):
        successful_call = self.loop.run_until_complete(
            _run_in_another_process(_grpc_aio_call, self.server_target))
        self.assertEqual(successful_call, True)


class TestInsecureChannel(test_base.AioTestBase):

    def test_insecure_channel(self):

        async def coro():
            channel = aio.insecure_channel(self.server_target)
            self.assertIsInstance(channel, aio.Channel)

        self.loop.run_until_complete(coro())


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main(verbosity=2)
