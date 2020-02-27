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

import socket as native_socket

from libc cimport string

cdef int _ASYNCIO_STREAM_DEFAULT_SOCKET_BACKLOG = 100


# TODO(https://github.com/grpc/grpc/issues/21348) Better flow control needed.
cdef class _AsyncioSocket:
    def __cinit__(self):
        self._grpc_socket = NULL
        self._grpc_connect_cb = NULL
        self._grpc_read_cb = NULL
        self._grpc_write_cb = NULL
        self._reader = None
        self._writer = None
        self._task_connect = None
        self._task_read = None
        self._task_write = None
        self._read_buffer = NULL
        self._server = None
        self._py_socket = None
        self._peername = None
        self._io_loop = None
        self._loop = None 

    @staticmethod
    cdef _AsyncioSocket create(grpc_custom_socket * grpc_socket,
                               object reader,
                               object writer):
        socket = _AsyncioSocket()
        socket._grpc_socket = grpc_socket
        socket._reader = reader
        socket._writer = writer
        if writer is not None:
            socket._peername = writer.get_extra_info('peername')
        socket._io_loop = _current_io_loop()
        socket._loop = _current_io_loop().asyncio_loop()
        return socket

    @staticmethod
    cdef _AsyncioSocket create_with_py_socket(grpc_custom_socket * grpc_socket, object py_socket):
        socket = _AsyncioSocket()
        socket._grpc_socket = grpc_socket
        socket._py_socket = py_socket
        socket._io_loop = _current_io_loop()
        socket._loop = _current_io_loop().asyncio_loop()
        return socket

    def __repr__(self):
        class_name = self.__class__.__name__ 
        id_ = id(self)
        connected = self.is_connected()
        return f"<{class_name} {id_} connected={connected}>"

    def _connect_cb(self, future):
        cdef grpc_error* error
        cdef grpc_custom_connect_callback connect_cb = self._grpc_connect_cb
        cdef grpc_custom_socket* socket = <grpc_custom_socket*>self._grpc_socket

        self._task_connect = None
        try:
            self._reader, self._writer = future.result()
        except Exception as e:
            error = grpc_socket_error("Socket connect failed: {}".format(e).encode())
            with nogil:
                connect_cb(socket, error)
        else:
            # gRPC default posix implementation disables nagle
            # algorithm.
            sock = self._writer.transport.get_extra_info('socket')
            sock.setsockopt(native_socket.IPPROTO_TCP, native_socket.TCP_NODELAY, True)

            with nogil:
                connect_cb(socket, <grpc_error*>0)

        self._io_loop.io_mark()

    async def _async_read(self, size_t length):
        cdef int len_inbound_buffer
        cdef grpc_error* error
        cdef grpc_custom_read_callback read_cb = self._grpc_read_cb
        cdef grpc_custom_socket* socket = <grpc_custom_socket*>self._grpc_socket

        self._task_read = None
        try:
            inbound_buffer = await self._reader.read(n=length)
        except ConnectionError as e:
            error = grpc_socket_error("Read failed: {}".format(e).encode())
            with nogil:
                read_cb(socket, -1, error)
        else:
            string.memcpy(
                <void*>self._read_buffer,
                <char*>inbound_buffer,
                len(inbound_buffer)
            )
            len_inbound_buffer = len(inbound_buffer)
            with nogil:
                read_cb(socket, len_inbound_buffer, <grpc_error*>0)

        self._io_loop.io_mark()

    cdef void connect(self,
                      object host,
                      object port,
                      grpc_custom_connect_callback grpc_connect_cb):
        assert not self._reader
        assert not self._task_connect

        def callback():
            self._task_connect = asyncio.ensure_future(
                asyncio.open_connection(host, port),
                loop=self._loop
            )
            self._grpc_connect_cb = grpc_connect_cb
            self._task_connect.add_done_callback(self._connect_cb)

        self._loop.call_soon_threadsafe(callback)

    cdef void read(self, char * buffer_, size_t length, grpc_custom_read_callback grpc_read_cb):
        assert not self._task_read

        def callback():
            self._grpc_read_cb = grpc_read_cb
            self._read_buffer = buffer_
            self._task_read =  self._loop.create_task(self._async_read(length))

        self._loop.call_soon_threadsafe(callback)


    async def _async_write(self, bytearray outbound_buffer):
        cdef grpc_error* error
        cdef grpc_custom_write_callback write_cb = self._grpc_write_cb
        cdef grpc_custom_socket* socket = <grpc_custom_socket*>self._grpc_socket

        self._writer.write(outbound_buffer)
        self._task_write = None
        try:
            await self._writer.drain()
            with nogil:
                write_cb(socket, <grpc_error*>0)
        except ConnectionError as connection_error:
            error = grpc_socket_error("Socket write failed: {}".format(connection_error).encode())
            with nogil:
                write_cb(socket, error)

        self._io_loop.io_mark()

    cdef void write(self, grpc_slice_buffer * g_slice_buffer, grpc_custom_write_callback grpc_write_cb):
        """Performs write to network socket in AsyncIO.
        
        For each socket, Core guarantees there'll be only one ongoing write.
        When the write is finished, we need to call grpc_write_cb to notify
        Core that the work is done.
        """
        assert not self._task_write
        cdef char* start
        cdef bytearray outbound_buffer = bytearray()
        for i in range(g_slice_buffer.count):
            start = grpc_slice_buffer_start(g_slice_buffer, i)
            length = grpc_slice_buffer_length(g_slice_buffer, i)
            outbound_buffer.extend(<bytes>start[:length])

        def callback():
            self._grpc_write_cb = grpc_write_cb
            self._task_write = self._loop.create_task(self._async_write(outbound_buffer))

        self._loop.call_soon_threadsafe(callback)

    cdef bint is_connected(self):
        return self._reader and not self._reader._transport.is_closing()

    cdef void close(self):
        if self.is_connected():
            self._writer.close()
        if self._server:
            self._server.close()
        # NOTE(lidiz) If the asyncio.Server is created from a Python socket,
        # the server.close() won't release the fd until the close() is called
        # for the Python socket.
        if self._py_socket:
            self._py_socket.close()

    def _new_connection_callback(self, object reader, object writer):
        cdef grpc_error* error
        cdef grpc_custom_accept_callback accept_cb = self._grpc_accept_cb
        cdef grpc_custom_socket* socket = <grpc_custom_socket*>self._grpc_socket
        cdef grpc_custom_socket* client_socket = <grpc_custom_socket*>self._grpc_client_socket

        # Close the connection if server is not started yet.
        if accept_cb == NULL:
            writer.close()
            return

        py_client_socket = _AsyncioSocket.create(
            client_socket,
            reader,
            writer,
        )

        client_socket.impl = <void*>py_client_socket
        cpython.Py_INCREF(py_client_socket)  # Py_DECREF in asyncio_socket_destroy
        # Accept callback expects to be called with:
        # * grpc_custom_socket: A grpc custom socket for server
        # * grpc_custom_socket: A grpc custom socket for client (with new Socket instance)
        # * grpc_error: An error object
        error = grpc_error_none()
        with nogil:
            accept_cb(socket, client_socket, error)

        self._io_loop.io_mark()

    cdef listen(self):
        self._py_socket.listen(_ASYNCIO_STREAM_DEFAULT_SOCKET_BACKLOG)

        def callback():
            async def create_asyncio_server():
                self._server = await asyncio.start_server(
                    self._new_connection_callback,
                    sock=self._py_socket,
                )

            self._loop.create_task(create_asyncio_server())

        self._loop.call_soon_threadsafe(callback)

    cdef accept(self,
                grpc_custom_socket* grpc_socket_client,
                grpc_custom_accept_callback grpc_accept_cb):
        self._grpc_client_socket = grpc_socket_client
        self._grpc_accept_cb = grpc_accept_cb

    cdef tuple peername(self):
        return self._peername

    cdef tuple sockname(self):
        return self._py_socket.getsockname()
