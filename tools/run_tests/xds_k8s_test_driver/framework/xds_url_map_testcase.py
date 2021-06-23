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
"""A test framework built for urlMap related xDS test cases."""

import abc
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Tuple, Union

import grpc
from absl import flags, logging
from absl.testing import absltest
from google.protobuf import json_format

from framework import xds_k8s_testcase, xds_url_map_test_resources
from framework.rpc import grpc_testing
from framework.test_app import client_app

# Load existing flags
flags.adopt_module_key_flags(xds_k8s_testcase)
flags.adopt_module_key_flags(xds_url_map_test_resources)

# Define urlMap specific flags
QPS = flags.DEFINE_integer('qps', default=25, help='The QPS client is sending')

# Test configs
_URL_MAP_PROPAGATE_TIMEOUT_SEC = 600
_URL_MAP_PROPAGATE_CHECK_INTERVAL_SEC = 2

# Type aliases
LoadBalancerAccumulatedStatsResponse = grpc_testing.LoadBalancerAccumulatedStatsResponse
XdsTestClient = client_app.XdsTestClient
GcpResourceManager = xds_url_map_test_resources.GcpResourceManager
HostRule = xds_url_map_test_resources.HostRule
PathMatcher = xds_url_map_test_resources.PathMatcher
JsonType = Any

# ProtoBuf translatable RpcType enums
RpcTypeUnaryCall = 'UNARY_CALL'
RpcTypeEmptyCall = 'EMPTY_CALL'


def _split_camel(s: str, delimiter: str = '-') -> str:
    """Turn camel case name to snake-case-like name."""
    return ''.join(delimiter + c.lower() if c.isupper() else c
                   for c in s).lstrip(delimiter)


class DumpedXdsConfig(dict):
    """A convenience class to check xDS config.

    Feel free to add more pre-compute fields.
    """

    def __init__(self, xds_json: JsonType):
        super().__init__(xds_json)
        self.json_config = xds_json
        self.lds = None
        self.rds = None
        self.cds = []
        self.eds = []
        self.endpoints = []
        for xds_config in self['xdsConfig']:
            try:
                if 'listenerConfig' in xds_config:
                    self.lds = xds_config['listenerConfig']['dynamicListeners'][
                        0]['activeState']['listener']
                elif 'routeConfig' in xds_config:
                    self.rds = xds_config['routeConfig']['dynamicRouteConfigs'][
                        0]['routeConfig']
                elif 'clusterConfig' in xds_config:
                    for cluster in xds_config['clusterConfig'][
                            'dynamicActiveClusters']:
                        self.cds.append(cluster['cluster'])
                elif 'endpointConfig' in xds_config:
                    for endpoint in xds_config['endpointConfig'][
                            'dynamicEndpointConfigs']:
                        self.eds.append(endpoint['endpointConfig'])
            except Exception as e:
                logging.debug('Parse dumped xDS config failed with %s: %s',
                              type(e), e)
        for endpoint_config in self.eds:
            for endpoint in endpoint_config.get('endpoints', {}):
                for lb_endpoint in endpoint.get('lbEndpoints', {}):
                    try:
                        if lb_endpoint['healthStatus'] == 'HEALTHY':
                            self.endpoints.append(
                                '%s:%s' % (lb_endpoint['endpoint']['address']
                                           ['socketAddress']['address'],
                                           lb_endpoint['endpoint']['address']
                                           ['socketAddress']['portValue']))
                    except Exception as e:
                        logging.debug('Parse endpoint failed with %s: %s',
                                      type(e), e)

    def __str__(self) -> str:
        return json.dumps(self, indent=2)


class RpcDistributionStats:
    """A convenience class to check RPC distribution.

    Feel free to add more pre-compute fields.
    """
    num_failures: int
    num_oks: int
    default_service_rpc_count: int
    alternative_service_rpc_count: int
    unary_call_default_service_rpc_count: int
    empty_call_default_service_rpc_count: int
    unary_call_alternative_service_rpc_count: int
    empty_call_alternative_service_rpc_count: int

    def __init__(self, json_lb_stats: JsonType):
        self.num_failures = json_lb_stats.get('numFailures', 0)

        self.num_oks = 0
        self.default_service_rpc_count = 0
        self.alternative_service_rpc_count = 0
        self.unary_call_default_service_rpc_count = 0
        self.empty_call_default_service_rpc_count = 0
        self.unary_call_alternative_service_rpc_count = 0
        self.empty_call_alternative_service_rpc_count = 0

        if 'rpcsByMethod' in json_lb_stats:
            for rpc_type in json_lb_stats['rpcsByMethod']:
                for peer in json_lb_stats['rpcsByMethod'][rpc_type][
                        'rpcsByPeer']:
                    count = json_lb_stats['rpcsByMethod'][rpc_type][
                        'rpcsByPeer'][peer]
                    self.num_oks += count
                    if rpc_type == 'UnaryCall':
                        if 'alternative' in peer:
                            self.unary_call_alternative_service_rpc_count = count
                            self.alternative_service_rpc_count += count
                        else:
                            self.unary_call_default_service_rpc_count = count
                            self.default_service_rpc_count += count
                    else:
                        if 'alternative' in peer:
                            self.empty_call_alternative_service_rpc_count = count
                            self.alternative_service_rpc_count += count
                        else:
                            self.empty_call_default_service_rpc_count = count
                            self.default_service_rpc_count += count


@dataclass
class ExpectedResult:
    """Describes the expected result of assertRpcStatusCode method below."""
    rpc_type: str = RpcTypeUnaryCall
    status_code: grpc.StatusCode = grpc.StatusCode.OK
    ratio: float = 1


class MetaXdsUrlMapTestCase(type):
    """Tracking test case subclasses."""

    # Automatic discover of all subclasses
    _test_case_classes = []
    _test_case_names = set()
    # Keep track of started and finished test cases, so we know when to setup
    # and tear down GCP resources.
    _started_test_cases = set()
    _finished_test_cases = set()

    def __new__(cls, name: str, bases: Iterable[Any],
                attrs: Mapping[str, Any]) -> Any:
        # Hand over the tracking objects
        attrs['test_case_classes'] = cls._test_case_classes
        attrs['test_case_names'] = cls._test_case_names
        attrs['started_test_cases'] = cls._started_test_cases
        attrs['finished_test_cases'] = cls._finished_test_cases
        # Handle the test name reflection
        module_name = os.path.split(
            sys.modules[attrs['__module__']].__file__)[-1]
        if module_name.endswith('_test.py'):
            module_name = module_name.replace('_test.py', '')
        attrs['short_module_name'] = module_name.replace('_', '-')
        # Create the class and track
        new_class = type.__new__(cls, name, bases, attrs)
        if name.startswith('Test'):
            cls._test_case_names.add(name)
            cls._test_case_classes.append(new_class)
        else:
            logging.info('Skipping test case class: %s', name)
        return new_class


class XdsUrlMapTestCase(absltest.TestCase, metaclass=MetaXdsUrlMapTestCase):
    """XdsUrlMapTestCase is the base class for urlMap related tests.

    The subclass is expected to implement 3 methods:

    - url_map_change: Updates the urlMap components for this test case
    - xds_config_validate: Validates if the client received legit xDS configs
    - rpc_distribution_validate: Validates if the routing behavior is correct
    """

    @staticmethod
    @abc.abstractmethod
    def url_map_change(
            host_rule: HostRule,
            path_matcher: PathMatcher) -> Tuple[HostRule, PathMatcher]:
        """Updates the dedicated urlMap components for this test case.

        Each test case will have a dedicated HostRule, where the hostname is
        generated from the test case name. The HostRule will be linked to a
        PathMatcher, where stores the routing logic.

        Args:
            host_rule: A HostRule GCP resource as a JSON dict.
            path_matcher: A PathMatcher GCP resource as a JSON dict.

        Returns:
            A tuple contains the updated version of given HostRule and
            PathMatcher.
        """
        pass

    @abc.abstractmethod
    def xds_config_validate(self, xds_config: DumpedXdsConfig) -> None:
        """Validates received xDS config, if anything is wrong, raise.

        This stage only ends when the control plane failed to send a valid
        config within a given time range, like 600s.

        Args:
            xds_config: A DumpedXdsConfig instance can be used as a JSON dict,
              but also provides helper fields for commonly checked xDS config.
        """
        pass

    @abc.abstractmethod
    def rpc_distribution_validate(self, client: XdsTestClient) -> None:
        """Validates the routing behavior, if any is wrong, raise.

        Args:
            client: A XdsTestClient instance for all sorts of end2end testing.
        """
        pass

    @classmethod
    def hostname(cls):
        return "%s.%s:%s" % (cls.short_module_name, _split_camel(
            cls.__name__), GcpResourceManager().server_xds_port)

    @classmethod
    def path_matcher_name(cls):
        # Path matcher name must match r'(?:[a-z](?:[-a-z0-9]{0,61}[a-z0-9])?)'
        return "%s-%s-pm" % (cls.short_module_name, _split_camel(cls.__name__))

    @classmethod
    def setUpClass(cls):
        if len(cls.started_test_cases) == 0:
            # Create the GCP resource once before the first test start
            GcpResourceManager().setup(cls.test_case_classes)
        cls.started_test_cases.add(cls.__name__)
        # TODO(lidiz) concurrency is possible, pending multiple-instance change
        GcpResourceManager().test_client_runner.cleanup(force=True)
        # Sending both RPCs when starting.
        cls.test_client = GcpResourceManager().test_client_runner.run(
            server_target=f'xds:///{cls.hostname()}',
            rpc='UnaryCall,EmptyCall',
            qps=QPS.value,
            print_response=True)

    @classmethod
    def tearDownClass(cls):
        GcpResourceManager().test_client_runner.cleanup(force=True)
        cls.finished_test_cases.add(cls.__name__)
        if cls.finished_test_cases == cls.test_case_names:
            # Tear down the GCP resource after all tests finished
            GcpResourceManager().tear_down()

    def test_client_config(self):
        """Continuously check if the latest client config is valid yet."""
        config = None
        json_config = None
        last_exception = None
        deadline = time.time() + _URL_MAP_PROPAGATE_TIMEOUT_SEC
        while time.time() < deadline:
            try:
                config = self.test_client.csds.fetch_client_status(
                    log_level=logging.INFO)
                if config is None:
                    # Client config is empty, skip this run
                    json_config = None
                else:
                    # Found client config, testing it.
                    json_config = json_format.MessageToDict(config)
                    try:
                        self.xds_config_validate(DumpedXdsConfig(json_config))
                    except Exception as e:
                        # It's okay to fail, the xDS config might be
                        # incomplete/obsolete during the 600s time frame.
                        logging.info('xDS config check failed: %s: %s', type(e),
                                     e)
                        if type(last_exception) != type(e) or str(
                                last_exception) != str(e):
                            # Suppress repetitive exception logs
                            logging.exception(e)
                            last_exception = e
                    else:
                        # No exception raised, test PASSED!
                        logging.info('valid xDS config: %s',
                                     json.dumps(json_config, indent=2))
                        return
                # Wait a while until next attempt.
                time.sleep(_URL_MAP_PROPAGATE_CHECK_INTERVAL_SEC)
            except KeyboardInterrupt:
                # For active development, this clause allow developer to view
                # the failing xDS config quicker.
                logging.info('latest xDS config: %s',
                             json.dumps(json_config, indent=2))
                raise
        # Test FAILED!
        raise RuntimeError(
            'failed to receive valid xDS config within %s seconds, latest: %s' %
            (_URL_MAP_PROPAGATE_TIMEOUT_SEC, json.dumps(json_config, indent=2)))

    def test_rpc_distribution(self):
        self.rpc_distribution_validate(self.test_client)

    @staticmethod
    def configure_and_send(test_client: XdsTestClient,
                           *,
                           rpc_types: Iterable[str],
                           metadata: Optional[Iterable[Tuple[str, str,
                                                             str]]] = None,
                           app_timeout: Optional[int] = None,
                           num_rpcs: int) -> RpcDistributionStats:
        test_client.update_config.configure(rpc_types=rpc_types,
                                            metadata=metadata,
                                            app_timeout=app_timeout)
        json_lb_stats = json_format.MessageToDict(
            test_client.get_load_balancer_stats(num_rpcs=num_rpcs))
        logging.info(
            'Received LoadBalancerStatsResponse from test client %s:\n%s',
            test_client.ip, json.dumps(json_lb_stats, indent=2))
        return RpcDistributionStats(json_lb_stats)

    def assertNumEndpoints(self, xds_config: DumpedXdsConfig, k: int) -> None:
        self.assertEqual(
            k, len(xds_config.endpoints),
            f'insufficient endpoints in EDS: want={k} seen={xds_config.endpoints}'
        )

    def assertRpcStatusCode(self, test_client: XdsTestClient, *,
                            expected: Iterable[ExpectedResult], length: int,
                            tolerance: float) -> None:
        """Assert the distribution of RPC statuses over a period of time."""
        # Sending with pre-set QPS for a period of time
        before_stats = test_client.get_load_balancer_accumulated_stats()
        logging.info(
            'Received LoadBalancerAccumulatedStatsResponse from test client %s: before:\n%s',
            test_client.ip, before_stats)
        time.sleep(length)
        after_stats = test_client.get_load_balancer_accumulated_stats()
        logging.info(
            'Received LoadBalancerAccumulatedStatsResponse from test client %s: after: \n%s',
            test_client.ip, after_stats)
        # Validate the diff
        expected_total = length * QPS.value
        for expected_result in expected:
            rpc = expected_result.rpc_type
            status = expected_result.status_code.value[0]
            seen = after_stats.stats_per_method.get(rpc, {}).result.get(
                status, 0) - before_stats.stats_per_method.get(
                    rpc, {}).result.get(status, 0)
            total = sum(x[1]
                        for x in after_stats.stats_per_method.get(
                            rpc, {}).result.items()) - sum(
                                x[1] for x in before_stats.stats_per_method.get(
                                    rpc, {}).result.items())
            want = total * expected_result.ratio
            self.assertLessEqual(
                abs(seen - want) / total, tolerance,
                'Expect rpc [%s] to return [%s] at %.2f ratio: seen=%d want=%d total=%d diff_ratio=%.4f > %.2f'
                % (rpc, expected_result.status_code, expected_result.ratio,
                   seen, want, total, abs(seen - want) / total, tolerance))
