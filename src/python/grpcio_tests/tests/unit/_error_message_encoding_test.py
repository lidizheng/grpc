# -*- coding=utf-8 -*-
# Copyright 2018 gRPC authors.
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
"""Tests 'utf-8' encoded error message."""

import unittest
import weakref

import grpc
from grpc import _channel

from tests.unit import test_common
from tests.unit.framework.common import test_constants

_REQUEST = b'\x00\x00\x00'
_RESPONSE = b'\x00\x00\x00'

_UNARY_UNARY = '/test/UnaryUnary'


class _MethodHandler(grpc.RpcMethodHandler):
    
    def unary_unary(self, _, servicer_context):
        servicer_context.set_code(grpc.StatusCode.UNKNOWN)
        servicer_context.set_details(u'é')
        return _RESPONSE


class _GenericHandler(grpc.GenericRpcHandler):

    def __init__(self, test):
        self._test = test

    def service(self, handler_call_details):
        return _MethodHandler()


class ErrorMessageEncodingTest(unittest.TestCase):

    def setUp(self):
        self._server = test_common.test_server()
        self._server.add_generic_rpc_handlers((_GenericHandler(
            weakref.proxy(self)),))
        port = self._server.add_insecure_port('[::]:0')
        self._server.start()
        self._channel = grpc.insecure_channel('localhost:%d' % port)

    def tearDown(self):
        self._server.stop(0)

    def testMessageEncoding(self):
        multi_callable = self._channel.unary_unary(_UNARY_UNARY)
        _, call = multi_callable.with_call(_REQUEST)


if __name__ == '__main__':
    unittest.main(verbosity=2)
