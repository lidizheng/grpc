# Copyright 2019 gRPC authors.
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

import os
import subprocess
import sys

from concurrent import futures
from time import sleep

import grpc
from src.proto.grpc.testing import messages_pb2
from src.proto.grpc.testing import test_pb2_grpc

# TODO (https://github.com/grpc/grpc/issues/19762)
# Change for an asynchronous server version once it's implemented.


class TestServiceServicer(test_pb2_grpc.TestServiceServicer):

    def UnaryCall(self, request, context):
        return messages_pb2.SimpleResponse()


class Server:
    """
    Synchronous server is executed in another process which initializes
    implicitly the grpc using the synchronous configuration. Both worlds
    can not coexist within the same process.
    """

    def __init__(self, host_and_port):  # pylint: disable=W0621
        self._host_and_port = host_and_port
        self._handle = None

    def start(self):
        assert self._handle is None

        filename = os.path.abspath(__file__)
        args = ["python", filename, self._host_and_port]
        self._handle = subprocess.Popen(args)

    def terminate(self):
        if not self._handle:
            return

        self._handle.terminate()
        self._handle = None


if __name__ == "__main__":
    try:
        host_and_port = sys.argv[1]
    except IndexError:
        print("Missing host_and_port argument, like localhost:3333")
        sys.exit(1)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=1),
        options=(('grpc.so_reuseport', 1),))
    test_pb2_grpc.add_TestServiceServicer_to_server(TestServiceServicer(),
                                                    server)
    server.add_insecure_port(host_and_port)
    server.start()
    try:
        sleep(3600)
    finally:
        server.stop(None)
