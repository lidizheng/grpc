/*
 *
 * Copyright 2015 gRPC authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#ifndef GRPC_INTERNAL_COMPILER_PYTHON_PRIVATE_GENERATOR_H
#define GRPC_INTERNAL_COMPILER_PYTHON_PRIVATE_GENERATOR_H

#include <iostream>
#include <vector>

#include "src/compiler/python_generator.h"
#include "src/compiler/schema_interface.h"

namespace grpc_python_generator {

namespace {

// Tucks all generator state in an anonymous namespace away from
// PythonGrpcGenerator and the header file, mostly to encourage future changes
// to not require updates to the grpcio-tools C++ code part. Assumes that it is
// only ever used from a single thread.
struct PrivateGenerator {
  const GeneratorConfiguration& config;
  const grpc_generator::File* file;

  bool generate_in_pb2_grpc;

  PrivateGenerator(const GeneratorConfiguration& config,
                   const grpc_generator::File* file);

  std::pair<bool, grpc::string> GetGrpcServices();

 private:
  bool PrintPreamble(grpc_generator::Printer* out);
  bool PrintBetaPreamble(grpc_generator::Printer* out);
  bool PrintGAServices(grpc_generator::Printer* out);
  bool PrintBetaServices(grpc_generator::Printer* out);

  bool PrintAddServicerToServer(
      const grpc::string& package_qualified_service_name,
      const grpc_generator::Service* service, grpc_generator::Printer* out);
  bool PrintServicer(const grpc_generator::Service* service,
                     grpc_generator::Printer* out);
  bool PrintStub(const grpc::string& package_qualified_service_name,
                 const grpc_generator::Service* service,
                 grpc_generator::Printer* out);

  bool PrintBetaServicer(const grpc_generator::Service* service,
                         grpc_generator::Printer* out);
  bool PrintBetaServerFactory(
      const grpc::string& package_qualified_service_name,
      const grpc_generator::Service* service, grpc_generator::Printer* out);
  bool PrintBetaStub(const grpc_generator::Service* service,
                     grpc_generator::Printer* out);
  bool PrintBetaStubFactory(const grpc::string& package_qualified_service_name,
                            const grpc_generator::Service* service,
                            grpc_generator::Printer* out);

  // Get all comments (leading, leading_detached, trailing) and print them as a
  // docstring. Any leading space of a line will be removed, but the line
  // wrapping will not be changed.
  void PrintAllComments(std::vector<grpc::string> comments,
                        grpc_generator::Printer* out);

  // Provides RAII indentation handling. Use as:
  // {
  //   IndentScope raii_my_indent_var_name_here(my_py_printer);
  //   // constructor indented my_py_printer
  //   ...
  //   // destructor called at end of scope, un-indenting my_py_printer
  // }
  class IndentScope {
  public:
    explicit IndentScope(grpc_generator::Printer* printer) : printer_(printer) {
      for (int i=0;i<config->indent_size;i+=2) printer_->Indent();
    }

    ~IndentScope() { for (int i=0;i<config->indent_size;i+=2) printer_->Outdent(); }

  private:
    grpc_generator::Printer* printer_;
  };
};

}  // namespace

}  // namespace grpc_python_generator

#endif  // GRPC_INTERNAL_COMPILER_PYTHON_PRIVATE_GENERATOR_H
