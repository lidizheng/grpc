#!/usr/bin/env python3
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
"""Generate build metadata for external protos (mostly xDS-related).

The build metadata will be used in CMakeLists to ensure xDS proto dependencies
are present before compilation.
"""

import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import List

import yaml


@dataclass()
class ExternalProtoLibrary:
    # The relative path of this proto library should be. Preferably, it should
    # match the submodule path.
    destination: str
    # The prefix to remove in order to insure the proto import is correct. For
    # more info, see description of https://github.com/grpc/grpc/pull/25272.
    proto_prefix: str
    # Following 3 fields should be filled by build metadata from Bazel.
    url: str = ''
    hash: str = ''
    strip_prefix: str = ''


EXTERNAL_PROTO_LIBRARIES = {
    'envoy_api':
        ExternalProtoLibrary(destination='third_party/envoy-api',
                             proto_prefix='third_party/envoy-api/'),
    'com_google_googleapis':
        ExternalProtoLibrary(destination='third_party/googleapis',
                             proto_prefix='third_party/googleapis/'),
    'com_github_cncf_udpa':
        ExternalProtoLibrary(destination='third_party/udpa',
                             proto_prefix='third_party/udpa/'),
    'com_envoyproxy_protoc_gen_validate':
        ExternalProtoLibrary(destination='third_party/protoc-gen-validate',
                             proto_prefix='third_party/protoc-gen-validate/'),
    'opencensus_proto':
        ExternalProtoLibrary(destination='third_party/opencensus-proto',
                             proto_prefix='third_party/opencensus-proto/src/'),
}


@dataclass()
class _HttpArchive:
    name: str = ''
    url: str = ''
    hash: str = ''
    strip_prefix: str = ''


def _fetch_raw_http_archives() -> ET.Element:
    """Get xml output of bazel query invocation, parsed as XML tree"""
    output = subprocess.check_output([
        'tools/bazel', 'query', '--output', 'xml',
        'kind(http_archive, //external:*)'
    ])
    return ET.fromstring(output)


def _parse_http_archives(xml_tree: ET.Element) -> List[ExternalProtoLibrary]:
    result = []
    for xml_http_archive in xml_tree:
        if xml_http_archive.tag != 'rule' or xml_http_archive.attrib[
                'class'] != 'http_archive':
            continue
        http_archive = _HttpArchive()
        for xml_node in xml_http_archive:
            if xml_node.attrib['name'] == 'name':
                http_archive.name = xml_node.attrib['value']
            if xml_node.attrib['name'] == 'urls':
                http_archive.url = xml_node[0].attrib['value']
            if xml_node.attrib['name'] == 'url':
                http_archive.url = xml_node.attrib['value']
            if xml_node.attrib['name'] == 'sha256':
                http_archive.hash = xml_node.attrib['value']
            if xml_node.attrib['name'] == 'strip_prefix':
                http_archive.strip_prefix = xml_node.attrib['value']
        if http_archive.name not in EXTERNAL_PROTO_LIBRARIES:
            continue
        lib = EXTERNAL_PROTO_LIBRARIES[http_archive.name]
        lib.url = http_archive.url
        lib.hash = http_archive.hash
        lib.strip_prefix = http_archive.strip_prefix
        result.append(lib)
    return result


def main():
    xml_tree = _fetch_raw_http_archives()
    libraries = _parse_http_archives(xml_tree)
    libraries.sort(key=lambda x: x.destination)
    print(yaml.dump(dict(external_libraries=list(map(asdict, libraries)))))


if __name__ == '__main__':
    main()
