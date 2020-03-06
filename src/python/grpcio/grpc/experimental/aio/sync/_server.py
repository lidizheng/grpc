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

import grpc
from grpc.experimental import aio
from grpc._cython import cygrpc
import threading


class Server(grpc.Server):

    def __init__(self, thread_pool, generic_handlers, interceptors, options,
                 maximum_concurrent_rpcs, compression):
        self._async_server = cygrpc.grpc_run_in_event_loop_thread(
            lambda: aio._server.Server(thread_pool, generic_handlers,
                                       interceptors, options,
                                       maximum_concurrent_rpcs, compression))

    def add_generic_rpc_handlers(self, generic_rpc_handlers):
        self._async_server.add_generic_rpc_handlers(generic_rpc_handlers)

    def add_insecure_port(self, address):
        return self._async_server.add_insecure_port(address)

    def add_secure_port(self, address, server_credentials):
        return self._async_server.add_secure_port(address, server_credentials)

    def start(self):
        return cygrpc.grpc_await(self._async_server.start())

    def wait_for_termination(self, timeout=None):
        return cygrpc.grpc_await(
            self._async_server.wait_for_termination(timeout))

    def stop(self, grace):
        return cygrpc.grpc_await(self._async_server.stop(grace))

    def __del__(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_server.__del__)


class SyncServicerContext(grpc.ServicerContext):

    def __cinit__(self, async_servicer_context):
        self._async_servicer_context = async_servicer_context

    def send_initial_metadata(self, metadata):
        cygrpc.grpc_await(
            self._async_servicer_context.send_initial_metadata(metadata))

    def abort(self, code, details=''):
        cygrpc.grpc_await(self._async_servicer_context.abort(code, details))

    def set_trailing_metadata(self, metadata):
        self._async_servicer_context.set_trailing_metadata(metadata)

    def invocation_metadata(self):
        return self._async_servicer_context.invocation_metadata()

    def set_code(self, code):
        self._async_servicer_context.set_code(code)

    def set_details(self, details):
        self._async_servicer_context.set_details(details)

    def set_compression(self, compression):
        self._async_servicer_context.set_compression(compression)

    def disable_next_message_compression(self):
        self._async_servicer_context.disable_next_message_compression()
