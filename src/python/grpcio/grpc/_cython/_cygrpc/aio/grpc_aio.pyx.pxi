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


# This is a testing environment variable that helps validation of the
# sync-over-async stack. This should not be used in production since users
# should provide their event loop.
_GRPC_TEST_ENABLE_ASYNCIO = (
    os.environ.get('GRPC_TEST_ENABLE_ASYNCIO', '0').lower() in _TRUE_VALUES)


cdef bint _grpc_aio_initialized = False
# NOTE(lidiz) Theoretically, applications can run in multiple event loops as
# long as they are in the same thread with same magic. However, I don't think
# we should support this use case. So, the gRPC Python Async Stack should be
# used in a one-and-only event loop picked by "init_grpc_aio".
cdef object _grpc_aio_loop
cdef object _event_loop_thread_ident


def init_grpc_aio(background=False):
    global _grpc_aio_initialized
    global _grpc_aio_loop

    if _grpc_aio_initialized:
        return
    else:
        _grpc_aio_initialized = True

    # Anchors the event loop that the gRPC library going to use.
    if background:
        _spawn_background_event_loop()
    else:
        _grpc_aio_loop = asyncio.get_event_loop()
        _event_loop_thread_ident = threading.current_thread().ident

    # Activates asyncio IO manager
    install_asyncio_iomgr()

    # TODO(lidiz) we need a the grpc_shutdown_blocking() counterpart for this
    # call. Otherwise, the gRPC library won't shutdown cleanly.
    grpc_init()

    # Timers are triggered by the Asyncio loop. We disable
    # the background thread that is being used by the native
    # gRPC iomgr.
    grpc_timer_manager_set_threading(False)

    # gRPC callbaks are executed within the same thread used by the Asyncio
    # event loop, as it is being done by the other Asyncio callbacks.
    Executor.SetThreadingAll(False)

    _grpc_aio_initialized = False


def grpc_aio_loop():
    """Returns the one-and-only gRPC Aio event loop."""
    return _grpc_aio_loop


def grpc_schedule_coroutine(object coro):
    """Thread-safely schedules coroutine to gRPC Aio event loop.
    If invoked within the same thread as the event loop, return an
    Asyncio.Task. Otherwise, return a concurrent.futures.Future (the sync
    Future). For non-asyncio threads, sync Future objects are probably easier
    to handle (without worrying other thread-safety stuff).
    """
    if _event_loop_thread_ident == threading.current_thread().ident:
        return _grpc_aio_loop.create_task(coro)
    else:
        return asyncio.run_coroutine_threadsafe(coro, _grpc_aio_loop)


def grpc_run_in_event_loop_thread(object func):
    if _event_loop_thread_ident == threading.current_thread().ident:
        return func()
    else:
        async def wrapper():
            return func()

        return asyncio.run_coroutine_threadsafe(wrapper(), _grpc_aio_loop).result()


def grpc_await(object coro):
    if _event_loop_thread_ident == threading.current_thread().ident:
        raise UsageError('Please invoke `grpc_await` on non-event-loop thread')

    async def await_result():
        return await coro

    return grpc_schedule_coroutine(await_result()).result()


def _spawn_background_event_loop():
    loop_ready = threading.Event()
    def async_event_loop():
        global _grpc_aio_loop
        global _event_loop_thread_ident

        # Creates event loop for the new thread
        _grpc_aio_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_grpc_aio_loop)

        _grpc_aio_loop.set_debug(True)
        loop_ready.set()
        _event_loop_thread_ident = threading.current_thread().ident
        _grpc_aio_loop.run_forever()

    thread = threading.Thread(target=async_event_loop)
    thread.daemon = True
    thread.start()
    loop_ready.wait()


if _GRPC_TEST_ENABLE_ASYNCIO:
    init_grpc_aio(background=True)
