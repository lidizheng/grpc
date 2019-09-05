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


cdef bint _grpc_aio_initialized = 0


cdef void _aio_prefork() nogil:
    # Since Aio runs with only one thread, the main one. We dont need to
    # shutdown gracefully background threads.
    pass

cdef void _aio_postfork_parent() nogil:
    # Since Aio runs with only one thread, the main one. We dont need to
    # restart background threads.
    pass

cdef void _aio_postfork_child() nogil:
    # gRPC library is shut down and the default iomgr is installed. The forked
    # process will have the responsability of initializing the gRPC library.
    with gil:
        global _grpc_aio_initialized

        grpc_shutdown_blocking()

        # Without this the forked process wouldn't be able to start the gRPC library
        # using the default iomgr since the custom iomgr is not wipped out. Executing
        # the `grpc_set_default_iomgr_platform` function installs the default iomgr which
        # later can be overriden by a custom iomgr.
        grpc_set_default_iomgr_platform()

        _grpc_aio_initialized = 0

def init_grpc_aio():
    global _grpc_aio_initialized

    if _grpc_aio_initialized:
        return

    install_asyncio_iomgr()
    grpc_init()

    # Timers are triggered by the Asyncio loop. We disable
    # the background thread that is being used by the native
    # gRPC iomgr.
    grpc_timer_manager_set_threading(0)

    # gRPC callbaks are executed within the same thread used by the Asyncio
    # event loop, as it is being done by the other Asyncio callbacks.
    Executor.SetThreadingAll(0)

    IF UNAME_SYSNAME != "Windows":
        # gRPC does not execute the fork handles when the iomgr is customized,
        # as it is the case of Aio which uses the Asyncio iomgr. We install our
        # own ones for making sure that the forked process is executed in a
        # healthy gRPC environment.
        pthread_atfork(&_aio_prefork, &_aio_postfork_parent, &_aio_postfork_child)
    ELSE:
        # There is no support for having a clean and healthy environment after
        # forking in none posix enviornments. As a result, after a fork the
        # the behavior is unpredictable.
        pass

    _grpc_aio_initialized = 1
