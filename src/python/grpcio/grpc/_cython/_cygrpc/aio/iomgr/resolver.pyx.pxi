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


cdef class _AsyncioResolver:
    def __cinit__(self):
        self._grpc_resolver = NULL
        self._task_resolve = None
        self._loop = None

    @staticmethod
    cdef _AsyncioResolver create(grpc_custom_resolver* grpc_resolver):
        resolver = _AsyncioResolver()
        resolver._grpc_resolver = grpc_resolver
        resolver._loop = _current_io_loop().asyncio_loop()
        return resolver

    def __repr__(self):
        class_name = self.__class__.__name__ 
        id_ = id(self)
        return f"<{class_name} {id_}>"

    def _resolve_cb(self, future):
        cdef grpc_resolved_addresses* addresses
        cdef grpc_error* g_error
        cdef grpc_custom_resolver* resolver = <grpc_custom_resolver*> self._grpc_resolver

        error = False
        try:
            res = future.result()
        except Exception as e:
            error = True
            error_msg = str(e)
        finally:
            self._task_resolve = None

        if not error:
            g_error = grpc_error_none()
            addresses = tuples_to_resolvaddr(res)
            with nogil:
                grpc_custom_resolve_callback(
                    resolver,
                    addresses,
                    g_error
                )
        else:
            g_error = grpc_socket_error("getaddrinfo {}".format(error_msg).encode())
            with nogil:
                grpc_custom_resolve_callback(
                    resolver,
                    NULL,
                    g_error
                )

        _current_io_loop().io_mark()

    cdef void resolve(self, char* host, char* port):
        assert not self._task_resolve

        def callback():
            self._task_resolve = asyncio.ensure_future(
                self._loop.getaddrinfo(host, port),
                loop=self._loop
            )
            self._task_resolve.add_done_callback(self._resolve_cb)

        self._loop.call_soon_threadsafe(callback)
