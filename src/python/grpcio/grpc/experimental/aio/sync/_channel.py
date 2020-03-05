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


class _ShadowRendezvous(grpc.RpcError, grpc.Call, grpc.Future):
    """A shadow class that replaces the sync stack's implementation."""

    def __init__(self, async_call: aio.Call):
        self._async_call = async_call

    def is_active(self):
        return not self.done()

    def time_remaining(self):
        return self._async_call.time_remaining()

    def cancel(self):
        pass

    def add_callback(self, callback):
        pass

    def __iter__(self):
        return self

    def next(self):
        return self._next()

    def __next__(self):
        return self._next()

    def _next(self):
        raise NotImplementedError()

    def debug_error_string(self):
        raise NotImplementedError()

    def _repr(self):
        return repr(self._async_call)

    def __repr__(self):
        return self._repr()

    def __str__(self):
        return self._repr()

    def __del__(self):
        pass

    def initial_metadata(self):
        pass

    def trailing_metadata(self):
        pass

    def code(self):
        return cygrpc.grpc_schedule_coroutine(self._async_call.code()).result()

    def details(self):
        return cygrpc.grpc_schedule_coroutine(
            self._async_call.details()).result()

    def debug_error_string(self):
        return cygrpc.grpc_schedule_coroutine(
            self._async_call.debug_error_string()).result()

    def cancelled(self):
        pass

    def running(self):
        pass

    def done(self):
        return cygrpc.grpc_run_in_event_loop_thread(self._async_call.done)

    def result(self, timeout=None):
        if timeout is not None:
            raise NotImplementedError()
        else:

            async def await_result():
                return await self._async_call

            return cygrpc.grpc_schedule_coroutine(await_result()).result()

    def exception(self, timeout=None):
        pass

    def traceback(self, timeout=None):
        pass

    def add_done_callback(self, fn):
        pass

    def _next(self):
        pass


class _UnaryUnaryMultiCallable(grpc.UnaryUnaryMultiCallable):

    def __init__(self, async_multicallable):
        self._async_multicallable = async_multicallable

    def __call__(self, *args, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(*args, **kwargs))
        shadow_rendezvous = _ShadowRendezvous(call)
        return shadow_rendezvous.result()

    def with_call(self, *args, **kwargs):
        call = cygrpc.grpc_run_in_event_loop_thread(
            lambda: self._async_multicallable(*args, **kwargs))
        shadow_rendezvous = _ShadowRendezvous(call)
        return shadow_rendezvous.result(), shadow_rendezvous

    def future(self,
               request,
               timeout=None,
               metadata=None,
               credentials=None,
               wait_for_ready=None,
               compression=None):
        call = self._async_multicallable(request, timeout, metadata,
                                         credentials, wait_for_ready,
                                         compression)
        return _ShadowRendezvous(call)


class Channel(grpc.Channel):
    """A cygrpc.Channel-backed implementation of grpc.Channel."""

    def __init__(self, target, options, credentials, compression):
        """Constructor.

        Args:
          target: The target to which to connect.
          options: Configuration options for the channel.
          credentials: A cygrpc.ChannelCredentials or None.
          compression: An optional value indicating the compression method to be
            used over the lifetime of the channel.
        """
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
        pass

    def stream_unary(self,
                     method,
                     request_serializer=None,
                     response_deserializer=None):
        pass

    def stream_stream(self,
                      method,
                      request_serializer=None,
                      response_deserializer=None):
        pass

    def _close(self):
        cygrpc.grpc_schedule_coroutine(self._async_channel.close()).result()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close()
        return False

    def close(self):
        self._close()

    def __del__(self):
        pass
