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
"""The Python AsyncIO Benchmark Clients."""

import abc
import asyncio
import time

import grpc
from grpc.experimental import aio

from src.proto.grpc.testing import (benchmark_service_pb2_grpc, control_pb2,
                                    messages_pb2)
from tests.qps import histogram
from tests.unit import resources


class GenericStub(object):

    def __init__(self, channel: aio.Channel):
        self.UnaryCall = channel.unary_unary(
            '/grpc.testing.BenchmarkService/UnaryCall')
        self.StreamingCall = channel.stream_stream(
            '/grpc.testing.BenchmarkService/StreamingCall')


class BenchmarkClient(abc.ABC):
    """Benchmark client interface that exposes a non-blocking send_request()."""

    def __init__(self, address: str, config: control_pb2.ClientConfig, hist: histogram.Histogram):
        # Creates the channel
        if config.HasField('security_params'):
            channel_credentials = grpc.ssl_channel_credentials(
                resources.test_root_certificates())
            self._channel = aio.secure_channel(address, channel_credentials, ((
                'grpc.ssl_target_name_override',
                config.security_params.server_host_override,
            ),))
        else:
            self._channel = aio.insecure_channel(address)

        # Creates the stub
        if config.payload_config.WhichOneof('payload') == 'simple_params':
            self._generic = False
            self._stub = benchmark_service_pb2_grpc.BenchmarkServiceStub(
                channel)
            payload = messages_pb2.Payload(
                body='\0' * config.payload_config.simple_params.req_size)
            self._request = messages_pb2.SimpleRequest(
                payload=payload,
                response_size=config.payload_config.simple_params.resp_size)
        else:
            self._generic = True
            self._stub = GenericStub(channel)
            self._request = '\0' * config.payload_config.bytebuf_params.req_size

        self._hist = hist
        self._response_callbacks = []
        self._concurrency = config.outstanding_rpcs_per_channel

    async def run(self) -> None:
        await aio.channel_ready(self._channel)

    async def stop(self) -> None:
        await self._channel.close()

    def _record_query_time(self, query_time: float) -> None:
        self._hist.add(query_time * 1e9)


class UnaryAsyncBenchmarkClient(BenchmarkClient):

    def __init__(self, address: str, config: control_pb2.ClientConfig, hist: histogram.Histogram):
        super().__init__(address, config, hist)
        self._running = None
        self._stopped = asyncio.Event()

    async def _send_request(self):
        start_time = time.time()
        await self._stub.UnaryCall(self._request)
        self._record_query_time(self, time.time() - start_time)

    async def _infinite_sender(self) -> None:
        while self._running:
            await self._send_request()

    async def run(self) -> None:
        await super().run()
        self._running = True
        senders = (self._infinite_sender() for _ in range(self._concurrency))
        await asyncio.wait(senders)
        self._stopped.set()
    
    async def stop(self) -> None:
        self._running = False
        await self._stopped.wait()
        await super().stop()


class StreamingAsyncBenchmarkClient(BenchmarkClient):

    def __init__(self, address: str, config: control_pb2.ClientConfig, hist: histogram.Histogram):
        super().__init__(address, config, hist)
        self._running = None
        self._stopped = asyncio.Event()

    async def _one_streamming_call(self):
        call = self._stub.StreamingCall()
        while self._running:
            start_time = time.time()
            await call.write(self._request)
            await call.read()
            self._record_query_time(self, time.time() - start_time)

    async def run(self):
        await super().run()
        self._running = True
        senders = (self._one_streamming_call() for _ in range(self._concurrency))
        await asyncio.wait(senders)
        self._stopped.set()

    async def stop(self):
        self._running = False
        await self._stopped.wait()
        await super().stop()