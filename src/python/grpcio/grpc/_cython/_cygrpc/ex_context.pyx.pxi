cdef extern from "Python.h":
    ctypedef cpython.PyObject *(*PyCFunction)(cpython.PyObject *, cpython.PyObject *)

    ctypedef struct PyMethodDef:
        # We don't care other fields
        PyCFunction  ml_meth

    ctypedef struct PyCFunctionObject:
        PyMethodDef         *m_ml
        cpython.PyObject    *m_self
        cpython.PyObject    *m_module

ctypedef enum RPC_TYPE:
    RPC_TYPE_UNKONWN
    RPC_TYPE_UNARY_UNARY
    RPC_TYPE_UNARY_STREAM
    RPC_TYPE_STREAM_UNARY
    RPC_TYPE_STREAM_STREAM

ctypedef struct CyMethodHandler:
    grpc_slice method
    RPC_TYPE rpc_type
    cpython.PyObject *behavior
    cpython.PyObject *request_deserializer
    cpython.PyObject *response_serializer

ctypedef struct CyGenericHandler:
    CyMethodHandler *method_handlers
    int num_method_handlers

    # In case of the generic handler can't be optimized.
    cpython.PyObject *original_generic_handler

    bint is_optimized

cdef faster_dictionary_generic_handler(
        object generic_handler,
        CyGenericHandler *cy_generic_handler):
    cy_generic_handler.is_optimized = True
    cy_generic_handler.original_generic_handler = <cpython.PyObject *>generic_handler
    cy_generic_handler.method_handlers = <CyMethodHandler *>gpr_malloc(
        sizeof(CyMethodHandler)*len(generic_handler._method_handlers))
    cy_generic_handler.num_method_handlers = len(generic_handler._method_handlers)

    cdef int cnt = 0
    cdef CyMethodHandler *cy_method_handler
    for method in generic_handler._method_handlers:
        cy_method_handler = &(cy_generic_handler.method_handlers[cnt])
        py_method_handler = generic_handler._method_handlers[method]
        cnt += 1

        cy_method_handler.method = _slice_from_bytes(_encode(method))
        cy_method_handler.request_deserializer = <cpython.PyObject *>py_method_handler.request_deserializer
        cy_method_handler.response_serializer = <cpython.PyObject *>py_method_handler.response_serializer
        if not py_method_handler.request_streaming and not py_method_handler.response_streaming:
            cy_method_handler.rpc_type = RPC_TYPE_UNARY_UNARY
            cy_method_handler.behavior = <cpython.PyObject *>py_method_handler.unary_unary

cdef wrap_generic_handler(
        object generic_handler,
        CyGenericHandler *cy_generic_handler):
    cy_generic_handler.is_optimized = False
    cy_generic_handler.original_generic_handler = <cpython.PyObject *>generic_handler
    cy_generic_handler.method_handlers = NULL
    cy_generic_handler.num_method_handlers = 0

cdef CyGenericHandler *optimize_generic_handlers(generic_handlers):
    cdef CyGenericHandler *c_handlers = <CyGenericHandler *>gpr_malloc(sizeof(CyGenericHandler)*len(generic_handlers))

    for i, generic_handler in enumerate(generic_handlers):
        if "DictionaryGenericHandler" in generic_handler.__class__.__name__:
            faster_dictionary_generic_handler(generic_handler, &c_handlers[i])
            print('FAST!', generic_handler.__class__.__name__, c_handlers[i].is_optimized)
        else:
            wrap_generic_handler(generic_handler, &c_handlers[i])
            print('WRAP!', generic_handler.__class__.__name__, c_handlers[i].is_optimized)
    return c_handlers


# class ExServicerContext(grpc.ServicerContext):

#     def __init__(self, rpc_event, state, request_deserializer):
#         self._rpc_event = rpc_event
#         self._state = state
#         self._request_deserializer = request_deserializer

#     def is_active(self):
#         with self._state.condition:
#             return self._state.client is not _CANCELLED and not self._state.statused

#     def time_remaining(self):
#         return max(self._rpc_event.call_details.deadline - time.time(), 0)

#     def cancel(self):
#         self._rpc_event.call.cancel()

#     def add_callback(self, callback):
#         with self._state.condition:
#             if self._state.callbacks is None:
#                 return False
#             else:
#                 self._state.callbacks.append(callback)
#                 return True

#     def disable_next_message_compression(self):
#         with self._state.condition:
#             self._state.disable_next_compression = True

#     def invocation_metadata(self):
#         return self._rpc_event.invocation_metadata

#     def peer(self):
#         return _common.decode(self._rpc_event.call.peer())

#     def peer_identities(self):
#         return cygrpc.peer_identities(self._rpc_event.call)

#     def peer_identity_key(self):
#         id_key = cygrpc.peer_identity_key(self._rpc_event.call)
#         return id_key if id_key is None else _common.decode(id_key)

#     def auth_context(self):
#         return {
#             _common.decode(key): value
#             for key, value in six.iteritems(
#                 cygrpc.auth_context(self._rpc_event.call))
#         }

#     def send_initial_metadata(self, initial_metadata):
#         with self._state.condition:
#             if self._state.client is _CANCELLED:
#                 _raise_rpc_error(self._state)
#             else:
#                 if self._state.initial_metadata_allowed:
#                     operation = cygrpc.SendInitialMetadataOperation(
#                         initial_metadata, _EMPTY_FLAGS)
#                     self._rpc_event.call.start_server_batch(
#                         (operation,), _send_initial_metadata(self._state))
#                     self._state.initial_metadata_allowed = False
#                     self._state.due.add(_SEND_INITIAL_METADATA_TOKEN)
#                 else:
#                     raise ValueError('Initial metadata no longer allowed!')

#     def set_trailing_metadata(self, trailing_metadata):
#         with self._state.condition:
#             self._state.trailing_metadata = trailing_metadata

#     def abort(self, code, details):
#         # treat OK like other invalid arguments: fail the RPC
#         if code == grpc.StatusCode.OK:
#             _LOGGER.error(
#                 'abort() called with StatusCode.OK; returning UNKNOWN')
#             code = grpc.StatusCode.UNKNOWN
#             details = ''
#         with self._state.condition:
#             self._state.code = code
#             self._state.details = _common.encode(details)
#             self._state.aborted = True
#             raise Exception()

#     def abort_with_status(self, status):
#         self._state.trailing_metadata = status.trailing_metadata
#         self.abort(status.code, status.details)

#     def set_code(self, code):
#         with self._state.condition:
#             self._state.code = code

#     def set_details(self, details):
#         with self._state.condition:
#             self._state.details = _common.encode(details)
