import queue

import grpc

from google.protobuf import descriptor_pb2, reflection
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc


def main():
    channel = grpc.insecure_channel('localhost:50051')
    stub = reflection_pb2_grpc.ServerReflectionStub(channel)

    # Establishes reflection RPC
    request_queue = queue.Queue(maxsize=1)
    response_iterator = stub.ServerReflectionInfo(iter(request_queue.get, None))

    # Queries available services (symbols)
    request_queue.put(reflection_pb2.ServerReflectionRequest(list_services=''))
    response = next(response_iterator)
    print(response)
    # Output:
    #     list_services_response {
    #     service {
    #         name: "grpc.reflection.v1alpha.ServerReflection"
    #     }
    #     service {
    #         name: "helloworld.Greeter"
    #     }
    #     }

    # Queries the proto file describing 'helloworld.Greeter'
    request_queue.put(
        reflection_pb2.ServerReflectionRequest(
            file_containing_symbol='helloworld.Greeter'))
    response = next(response_iterator)
    descriptors = response.file_descriptor_response.file_descriptor_proto
    raw_descriptor = descriptors[0]

    # Parse the proto file descriptor
    file_descriptor = descriptor_pb2.FileDescriptorProto.FromString(
        raw_descriptor)
    print(file_descriptor)
    # Output:
    #     name: "helloworld.proto"
    #     package: "helloworld"
    #     message_type {
    #       name: "HelloRequest"
    #       field {
    #         name: "name"
    #         number: 1
    #         label: LABEL_OPTIONAL
    #         type: TYPE_STRING
    #       }
    #     }
    #     message_type {
    #       name: "HelloReply"
    #       field {
    #         name: "message"
    #         number: 1
    #         label: LABEL_OPTIONAL
    #         type: TYPE_STRING
    #       }
    #     }
    #     service {
    #       name: "Greeter"
    #       method {
    #         name: "SayHello"
    #         input_type: ".helloworld.HelloRequest"
    #         output_type: ".helloworld.HelloReply"
    #         options {
    #         }
    #       }
    #     }
    #     options {
    #       java_package: "io.grpc.examples.helloworld"
    #       java_outer_classname: "HelloWorldProto"
    #       java_multiple_files: true
    #       objc_class_prefix: "HLW"
    #     }
    #     syntax: "proto3"


if __name__ == "__main__":
    main()
