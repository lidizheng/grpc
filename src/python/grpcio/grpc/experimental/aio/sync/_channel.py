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


class _ShadowRendezvous(grpc.RpcError, grpc.Call, grpc.Future):
    """A shadow class that replaces the sync stack's implementation."""

    def __init__(self, async_call: aio.Call, request_iterator=None):
        self._async_call = async_call
        if request_iterator:
            self._request_iterator = request_iterator
            self._request_iterator_consumer = threading.Thread(
                target=self._consume_request_iterator)
            self._request_iterator_consumer.daemon = True
            self._request_iterator_consumer.start()
        else:
            self._request_iterator = None
            self._request_iterator_consumer = None

    def _consume_request_iterator(self):
        for request in self._request_iterator:
            self._write(request)
        self._done_writing()

    def is_active(self):
        return not self.done()

    def time_remaining(self):
        return self._async_call.time_remaining()

    def cancel(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_call.cancel)

    def add_callback(self, callback):
        self._async_call.add_done_callback(lambda _: callback())

    def __iter__(self):
        return self

    def next(self):
        return self._next()

    def __next__(self):
        return self._next()

    def _next(self):
        message = cygrpc.grpc_await(self._async_call.read())
        if message is aio.EOF:
            raise StopIteration
        else:
            return message

    def _write(self, request):
        cygrpc.grpc_await(self._async_call.write(request))

    def _done_writing(self):
        cygrpc.grpc_await(self._async_call.done_writing())

    def _repr(self):
        return repr(self._async_call)

    def __repr__(self):
        return self._repr()

    def __str__(self):
        return self._repr()

    def __del__(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_call.__del__)

    def initial_metadata(self):
        return cygrpc.grpc_await(self._async_call.initial_metadata())

    def trailing_metadata(self):
        return cygrpc.grpc_await(self._async_call.trailing_metadata())

    def code(self):
        return cygrpc.grpc_await(self._async_call.code())

    def details(self):
        return cygrpc.grpc_await(self._async_call.details())

    def debug_error_string(self):
        return cygrpc.grpc_await(self._async_call.debug_error_string())

    def cancelled(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_call.cancelled)

    def running(self):
        return not self.done()

    def done(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_call.done)

    def result(self, timeout=None):
        if timeout is not None:
            raise NotImplementedError()
        else:
            return cygrpc.grpc_await(self._async_call)

    def exception(self, timeout=None):
        raise NotImplementedError()

    def traceback(self, timeout=None):
        raise NotImplementedError()

    def add_done_callback(self, fn):
        self._async_call.add_done_callback(fn)


class _UnaryUnaryMultiCallable(grpc.UnaryUnaryMultiCallable):

    def __init__(self, async_multicallable):
        self._async_multicallable = async_multicallable

    def __call__(self, request, **kwargs):
        return self.future(request, **kwargs).result()

    def with_call(self, request, **kwargs):
        future = self.future(request, **kwargs)
        return future.result(), future

    def future(self, request, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(request, **kwargs))
        return _ShadowRendezvous(call)


class _UnaryStreamMultiCallable(grpc.UnaryStreamMultiCallable):

    def __init__(self, async_multicallable):
        self._async_multicallable = async_multicallable

    def __call__(self, *args, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(*args, **kwargs))
        return _ShadowRendezvous(call)


class _StreamUnaryMultiCallable(grpc.StreamUnaryMultiCallable):

    def __init__(self, async_multicallable):
        self._async_multicallable = async_multicallable

    def __call__(self, request_iterator, **kwargs):
        return self.future(request_iterator, **kwargs).result()

    def with_call(self, request_iterator, **kwargs):
        future = self.future(request_iterator, **kwargs)
        return future.result(), future

    def future(self, request_iterator, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(**kwargs))
        return _ShadowRendezvous(call, request_iterator=request_iterator)


class _StreamStreamMultiCallable(grpc.StreamStreamMultiCallable):

    def __init__(self, async_multicallable):
        self._async_multicallable = async_multicallable

    def __call__(self, request_iterator, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(**kwargs))
        return _ShadowRendezvous(call, request_iterator)


class Channel(grpc.Channel):
    """A cygrpc.Channel-backed implementation of grpc.Channel."""

    def __init__(self, target, options, credentials, compression):
        self._async_channel = aio._channel.Channel(target, options, credentials,
                                                   compression, None)

    def subscribe(self, callback, try_to_connect=None):
        raise NotImplementedError()

    def unsubscribe(self, callback):
        raise NotImplementedError()

    def unary_unary(self,
                    method,
                    request_serializer=None,
                    response_deserializer=None):
        async_multicallable = self._async_channel.unary_unary(
            method, request_serializer, response_deserializer)
        return _UnaryUnaryMultiCallable(async_multicallable)

    def unary_stream(self,
                     method,
                     request_serializer=None,
                     response_deserializer=None):
        async_multicallable = self._async_channel.unary_stream(
            method, request_serializer, response_deserializer)
        return _UnaryStreamMultiCallable(async_multicallable)

    def stream_unary(self,
                     method,
                     request_serializer=None,
                     response_deserializer=None):
        async_multicallable = self._async_channel.stream_unary(
            method, request_serializer, response_deserializer)
        return _StreamUnaryMultiCallable(async_multicallable)

    def stream_stream(self,
                      method,
                      request_serializer=None,
                      response_deserializer=None):
        async_multicallable = self._async_channel.stream_stream(
            method, request_serializer, response_deserializer)
        return _StreamStreamMultiCallable(async_multicallable)

    def _close(self):
        return cygrpc.grpc_await(self._async_channel.close())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close()
        return False

    def close(self):
        self._close()

    def __del__(self):
        pass
