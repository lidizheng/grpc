from libc.stdio cimport printf
import threading
import collections
import multiprocessing


ctypedef enum TagType:
    TAG_TYPE_REQUEST_CALL
    TAG_TYPE_START_BATCH
    TAG_TYPE_SERVER_SHUTDOWN


ctypedef struct Tag:
    TagType tag_type


cdef (grpc_op*, int) ops_to_c_ops(object operations):
    if type(operations) not in [list, tuple]:
        return NULL, 0

    cdef int c_nops
    cdef grpc_op *c_ops
    c_nops = 0 if operations is None else len(operations)
    if c_nops > 0:
        c_ops = <grpc_op *>gpr_malloc(sizeof(grpc_op) * c_nops)
        for index, operation in enumerate(operations):
            (<Operation>operation).c()
            c_ops[index] = (<Operation>operation).c_op
    return c_ops, c_nops


cdef void finalize_ops(object operations, grpc_op* c_ops, int c_nops):
    if c_nops > 0:
        for index, operation in enumerate(operations):
            (<Operation>operation).c_op = c_ops[index]
            (<Operation>operation).un_c()
        gpr_free(c_ops)


cdef class HandlerCallDetails:
    cdef grpc_metadata_array *c_request_metadata
    cdef tuple _invocation_metadata
    cdef bytes _method

    def __cinit__(self, bytes method):
        self._method = method

    cdef _c(self, grpc_metadata_array *c_request_metadata):
        self.c_request_metadata = self.c_request_metadata

    @staticmethod
    cdef HandlerCallDetails create(bytes method, grpc_metadata_array *c_request_metadata):
        cdef HandlerCallDetails handler_call_details = HandlerCallDetails(method)
        handler_call_details._c(c_request_metadata)
        return handler_call_details

    @property
    def method(self):
        return self._method

    @property
    def invocation_metadata(self):
        if self._invocation_metadata is None:
            self._invocation_metadata = _metadata(self.c_request_metadata)
        return self._invocation_metadata


ctypedef enum ServerCallState:
    SERVER_CALL_STATE_UNKNOWN
    SERVER_CALL_STATE_SERVING
    SERVER_CALL_STATE_SHUTDOWN


cdef class ServerSyncCall:
    cdef grpc_server *c_server
    cdef CompletionQueue cq
    cdef grpc_call *c_call
    cdef CallDetails call_details
    cdef grpc_metadata_array c_request_metadata
    cdef ServerCallState state

    cdef int c_nops
    cdef grpc_op *c_ops

    cdef object invocation_metadata
    cdef grpc_event event
    cdef Tag *out_tag

    cdef HandlerCallDetails handler_call_details

    cdef _c(self, grpc_server *c_server, CompletionQueue cq):
        fork_handlers_and_grpc_init()
        self.c_server = c_server
        self.cq = cq
        self.c_call = NULL
        self.call_details = CallDetails()
        grpc_metadata_array_init(&self.c_request_metadata)
        self.state = SERVER_CALL_STATE_SERVING

    @staticmethod
    cdef ServerSyncCall create(grpc_server *c_server,
                           CompletionQueue cq):
        cdef ServerSyncCall server_sync_call = ServerSyncCall()
        server_sync_call._c(c_server, cq)
        return server_sync_call

    def shutdown(self):
        if self.state != SERVER_CALL_STATE_SERVING:
            raise RuntimeError('Server call failed to shutdown.')
        grpc_metadata_array_destroy(&self.c_request_metadata)
        grpc_shutdown()
        self.state = SERVER_CALL_STATE_SHUTDOWN
    
    cdef start_batch(self, object operations):
        self.c_ops, self.c_nops = ops_to_c_ops(operations)

        cdef Tag tag_start_batch
        tag_start_batch.tag_type = TAG_TYPE_START_BATCH

        with nogil:
            if GRPC_CALL_OK != grpc_call_start_batch(self.c_call,
                    self.c_ops, self.c_nops,
                    &tag_start_batch, NULL):
                with gil:
                    raise RuntimeError('Failed to start batch!')

        self.event = self.cq.next()
        assert &tag_start_batch == <Tag *>self.event.tag

        finalize_ops(operations, self.c_ops, self.c_nops)

    cdef bytes _receive_message(self):
        cdef Operation receive_message_operation = ReceiveMessageOperation(0)
        self.start_batch((
            receive_message_operation,
        ))
        return receive_message_operation.message()

    cdef void _send_message(self, bytes message):
        cdef list operations = [
            SendStatusFromServerOperation(
                None, StatusCode.ok, '', 0
            ),
            SendInitialMetadataOperation(None, 0),
            SendMessageOperation(message, 0)
        ]
        self.start_batch(operations)

    cdef void request(self) except *:
        cdef Tag tag_request_call
        tag_request_call.tag_type = TAG_TYPE_REQUEST_CALL
        
        with nogil:
            if GRPC_CALL_OK != grpc_server_request_call(
                    self.c_server, &self.c_call, &self.call_details.c_details,
                    &self.c_request_metadata,
                    self.cq.c_completion_queue,
                    self.cq.c_completion_queue, &tag_request_call):
                # The server is shutdown
                return

        self.event = self.cq.next()
        assert &tag_request_call == <Tag *>self.event.tag
        if not self.event.success:
            # The request call is cancelled or server is shutdown.
            with nogil:
                self.post_request_cleanup()
            return

        self.handler_call_details = HandlerCallDetails.create(
            self.call_details.method,
            &self.c_request_metadata
        )

    cdef void post_request_cleanup(self) nogil:
        grpc_slice_unref(self.call_details.c_details.method)
        grpc_slice_unref(self.call_details.c_details.host)
        grpc_call_unref(self.c_call)


cdef (void *, bint) get_method_handler_from_cy_generic_handlers(
        grpc_slice target_method,
        HandlerCallDetails handler_call_details,
        CyGenericHandler *cy_generic_handlers,
        int num_generic_handlers) nogil:
    for i in range(num_generic_handlers):
        if not cy_generic_handlers[i].is_optimized:
            # If not optimized, call Python "service" method.
            with gil:
                handler = (<object>(cy_generic_handlers[i].original_generic_handler)).service(
                    handler_call_details)
                if handler is not None:
                    return <cpython.PyObject *>handler, False
        else:
            # If optimized, inspect the methods in Cython.
            for i in range(num_generic_handlers):
                for j in range(cy_generic_handlers[i].num_method_handlers):
                    if grpc_slice_eq(
                            target_method,
                            cy_generic_handlers[i].method_handlers[j].method):
                        return &cy_generic_handlers[i].method_handlers[j], True
    # Return NULL if no behavior found
    return NULL, False


ctypedef enum ServerWorkerState:
    SERVER_WORKER_STATE_UNKNOWN
    SERVER_WORKER_STATE_SERVING
    SERVER_WORKER_STATE_SHUTTING_DOWN
    SERVER_WORKER_STATE_SHUTDOWN


cdef class ServerWorker:
    cdef grpc_server *c_server
    cdef CompletionQueue cq
    cdef ServerSyncCall server_call
    cdef ServerWorkerState state
    cdef CyGenericHandler *cy_generic_handlers
    cdef int num_generic_handlers

    def __cinit__(self, generic_rpc_handlers):
        self.cy_generic_handlers = optimize_generic_handlers(generic_rpc_handlers)
        self.num_generic_handlers = len(generic_rpc_handlers)

    cdef _c(self, grpc_server *c_server):
        fork_handlers_and_grpc_init()
        self.c_server = c_server
        self.cq = CompletionQueue()
        grpc_server_register_completion_queue(
            self.c_server,
            self.cq.c_completion_queue,
            NULL
        )
        self.server_call = ServerSyncCall.create(
            self.c_server,
            self.cq)
        self.state = SERVER_WORKER_STATE_SERVING

    @staticmethod
    cdef ServerWorker create(grpc_server *c_server, list generic_rpc_handlers):
        cdef ServerWorker server_worker = ServerWorker(generic_rpc_handlers)
        server_worker._c(c_server)
        return server_worker

    def shutdown(self):
        print('Server worker shutting down...')
        self.state = SERVER_WORKER_STATE_SHUTTING_DOWN

        self.cq.shutdown()
        self.server_call.shutdown()

        self.state = SERVER_WORKER_STATE_SHUTDOWN
        print('Server worker shutdown...')

    cdef void handle_unary_unary(self, rpc_method_handler):
        request = self.server_call._receive_message()

        if rpc_method_handler.request_deserializer is not None:
            request = rpc_method_handler.request_deserializer(request)

        response = rpc_method_handler.unary_unary(request, None)

        if rpc_method_handler.response_serializer is not None:
            response = rpc_method_handler.response_serializer(response)

        self.server_call._send_message(response)

    cdef void handle_unary_unary_cy(self, CyMethodHandler *cy_method_handler):
        cdef bytes request = self.server_call._receive_message()
        cdef object request_message
        cdef bytes response
        cdef object response_message
        cdef object behavior
        cdef object request_deserializer
        cdef object response_serializer

        behavior = <object>cy_method_handler.behavior
        if cy_method_handler.request_deserializer != NULL:
            request_deserializer = <object>cy_method_handler.request_deserializer
        if cy_method_handler.response_serializer != NULL:
            response_serializer = <object>cy_method_handler.response_serializer

        if request_deserializer is not None:
            request_message = request_deserializer(request)
        else:
            request_message = request

        # response_message = behavior(<object>c_result, None)
        response_message = behavior(request_message, None)

        if response_serializer is not None:
            response = response_serializer(response_message)
        else:
            response = response_message

        # response = request

        self.server_call._send_message(response)

    cdef void request(self):
        self.server_call.request()

        cdef void *method_handler_ptr
        cdef bint is_cy_method_handler
        with nogil:
            method_handler_ptr, is_cy_method_handler = get_method_handler_from_cy_generic_handlers(
                self.server_call.call_details.c_details.method,
                self.server_call.handler_call_details,
                self.cy_generic_handlers,
                self.num_generic_handlers
            )

        if method_handler_ptr != NULL:
            if is_cy_method_handler:
                self.handle_unary_unary_cy(<CyMethodHandler *>method_handler_ptr)
            else:
                self.handle_unary_unary(<object>method_handler_ptr)

        # This "nogil" is very important!!!!
        with nogil:
            self.server_call.post_request_cleanup()

    cpdef main_loop(self):
        print('Main Loop')
        while True:
            if self.state == SERVER_WORKER_STATE_SERVING:
                self.request()
                # self.server_call.request()
            else:
                break


ctypedef enum ServerState:
    SERVER_STATE_UNKNOWN
    SERVER_STATE_PREPARING
    SERVER_STATE_SERVING
    SERVER_STATE_SHUTTING_DOWN
    SERVER_STATE_SHUTDOWN


cdef class ExServer:
    cdef int num_threads
    cdef grpc_arg_pointer_vtable _vtable
    cdef grpc_server *c_server
    cdef list server_workers
    cdef list working_threads
    cdef CompletionQueue shutdown_cq
    cdef grpc_event event
    cdef ServerState state
    cdef list generic_rpc_handlers

    def __cinit__(self, int num_threads):
        fork_handlers_and_grpc_init()
        self.num_threads = num_threads
        self.server_workers = []
        self.working_threads = []
        self.generic_rpc_handlers = []
        self.shutdown_cq = CompletionQueue(shutdown_cq=True)

        self._vtable.copy = &_copy_pointer
        self._vtable.destroy = &_destroy_pointer
        self._vtable.cmp = &_compare_pointer
        cdef _ChannelArgs channel_args = _ChannelArgs.from_args(
            None, &self._vtable)
        self.c_server = grpc_server_create(
            channel_args.c_args(), NULL)

        
        # The state modification happens within Python layer, and thanks to GIL
        # there shouldn't be any consistency issue.
        self.state = SERVER_STATE_PREPARING

    def start(self):
        if self.state != SERVER_STATE_PREPARING:
            raise RuntimeError('Server failed to start. Please check if the ' +
                               'server is properly initialized and not ' +
                               'shutdown before.')

        for i in range(self.num_threads):
            self.server_workers.append(ServerWorker.create(
                self.c_server,
                self.generic_rpc_handlers
            ))

        with nogil:
            grpc_server_start(self.c_server)

        for i in range(self.num_threads):
            thread = threading.Thread(
                name="gRPC-ServerWorkingThread-%d" % i,
                target=self.server_workers[i].main_loop)
            thread.daemon = True
            thread.start()
            self.working_threads.append(thread)
        
        self.state = SERVER_STATE_SERVING

    def add_http2_port(self,
                       bytes address,
                       ServerCredentials server_credentials=None):
        if self.state != SERVER_STATE_PREPARING:
            raise RuntimeError('Server failed to add port. Please add http2 ' +
                               'port in preparing stage.')

        address = str_to_bytes(address)
        cdef int result
        cdef char *address_c_string = address
        with nogil:
            result = grpc_server_add_insecure_http2_port(self.c_server,
                                                         address_c_string)
        return result

    def add_generic_rpc_handlers(self, generic_rpc_handlers):
        for generic_rpc_handler in generic_rpc_handlers:
            self.generic_rpc_handlers.append(generic_rpc_handler)

    def stop(self):
        if self.state != SERVER_STATE_SERVING:
            raise RuntimeError('Server failed to stop. Please check if the ' +
                               'server is serving.')

        cdef Tag tag_server_shutdown
        tag_server_shutdown.tag_type = TAG_TYPE_SERVER_SHUTDOWN

        grpc_server_shutdown_and_notify(self.c_server,
                                        self.shutdown_cq.c_completion_queue,
                                        &tag_server_shutdown)
        grpc_server_cancel_all_calls(self.c_server)

        for i in range(self.num_threads):
            self.server_workers[i].shutdown()
            self.working_threads[i].join()

        while True:
            self.event = self.shutdown_cq.next()
            if &tag_server_shutdown == <Tag *>self.event.tag:
                print('Server SHUTDOWN Tag retrived')
                break
        
        grpc_server_destroy(self.c_server)


class NewServer:

    def __init__(self):
        self.ex_server = ExServer(
            num_threads=multiprocessing.cpu_count()
            # num_threads=1
        )

    def add_generic_rpc_handlers(self, generic_rpc_handlers):
        self.ex_server.add_generic_rpc_handlers(generic_rpc_handlers)

    def add_insecure_port(self, address):
        return self.ex_server.add_http2_port(address, None)

    def add_secure_port(self, address, server_credentials):
        return self.ex_server.add_http2_port(address, server_credentials._credentials)

    def start(self):
        self.ex_server.start()

    def stop(self, grace=None):
        self.ex_server.stop()


def have_fun():
    print('Having FUN!')


        # cdef cpython.PyCFunction c_func = PyCFunction_GET_FUNCTION(cy_method_handler.request_deserializer)
        # cdef cpython.PyObject *c_self = PyCFunction_GET_SELF(cy_method_handler.request_deserializer)
        # cdef cpython.PyObject *c_arg = 
        # cdef tuple args = (request,)
        # cdef cpython.PyObject *c_result
        # result = cpython.PyObject_CallObject(
        #     <object>cy_method_handler.request_deserializer,
        #     (request,))
        # cdef PyCFunctionObject *c_func = <PyCFunctionObject *>(cy_method_handler.request_deserializer)
        # cdef cpython.PyObject *c_result
        
        # c_result = c_func.m_ml.ml_meth(
        #     c_func.m_self,
        #     <cpython.PyObject *>request
        # )

