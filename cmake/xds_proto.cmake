# Copyright 2021 The gRPC Authors
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

set(_xDS_Proto_TEMPORARY_DIR ${CMAKE_BINARY_DIR}/xds_proto)
file(MAKE_DIRECTORY ${_xDS_Proto_TEMPORARY_DIR})

# This is bascially Bazel's http_archive.
# Note that strip_prefix strips the directory path prefix of the extracted
# archive contect, and it may strip multiple directory.
function(fetch_check_extract destination url hash strip_prefix)
  # Fetch and validate
  set(_xDS_Proto_TEMPORARY_FILE ${_xDS_Proto_TEMPORARY_DIR}/${strip_prefix}.tar.gz)
  file(DOWNLOAD ${url} ${_xDS_Proto_TEMPORARY_FILE}
       TIMEOUT 60
       EXPECTED_HASH SHA256=${hash}
       TLS_VERIFY ON)
  # Extract
  execute_process(COMMAND
                  ${CMAKE_COMMAND} -E tar xvf ${_xDS_Proto_TEMPORARY_FILE}
                  WORKING_DIRECTORY ${_xDS_Proto_TEMPORARY_DIR}
                  OUTPUT_QUIET)
  get_filename_component(_xDS_Proto_Destination_Path ${destination} DIRECTORY)
  file(MAKE_DIRECTORY ${_xDS_Proto_Destination_Path})
  file(RENAME ${_xDS_Proto_TEMPORARY_DIR}/${strip_prefix} ${destination})
  # Clean up
  file(REMOVE ${_xDS_Proto_TEMPORARY_DIR}/${strip_prefix})
  file(REMOVE ${_xDS_Proto_TEMPORARY_FILE})
endfunction()
