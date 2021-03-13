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

set(TEMPORARY_DIR ${CMAKE_BINARY_DIR}/xds_proto)
file(MAKE_DIRECTORY ${TEMPORARY_DIR})

# This is bascially Bazel http_archive.
function(fetch_check_extract destination url hash strip_prefix)
  # Fetch and validate
  set(TEMPORARY_FILE ${TEMPORARY_DIR}/${strip_prefix}.tar.gz)
  file(DOWNLOAD ${url} ${TEMPORARY_FILE}
       TIMEOUT 60
       EXPECTED_HASH SHA256=${hash}
       TLS_VERIFY ON)
  # Extract
  execute_process(COMMAND
                  ${CMAKE_COMMAND} -E tar xvf ${TEMPORARY_FILE}
                  WORKING_DIRECTORY ${TEMPORARY_DIR}
                  OUTPUT_QUIET)
  file(RENAME ${TEMPORARY_DIR}/${strip_prefix} ${destination})
  # Clean up
  file(REMOVE ${TEMPORARY_DIR}/${strip_prefix})
  file(REMOVE ${TEMPORARY_FILE})
endfunction()
