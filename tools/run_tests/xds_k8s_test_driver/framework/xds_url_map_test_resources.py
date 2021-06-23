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

import inspect
from typing import Any, Iterable, List, Mapping, Tuple

from absl import flags, logging

from framework import xds_flags, xds_k8s_flags
from framework.infrastructure import gcp, k8s, traffic_director
from framework.test_app import client_app, server_app

flags.adopt_module_key_flags(xds_flags)
flags.adopt_module_key_flags(xds_k8s_flags)

STRATEGY = flags.DEFINE_enum('strategy',
                             default='reuse',
                             enum_values=['create', 'keep', 'reuse'],
                             help='Strategy of GCP resources management')

# Type alias
UrlMapType = Any
HostRule = Any
PathMatcher = Any

_COMPUTE_V1_URL_PREFIX = 'https://www.googleapis.com/compute/v1'


class _UrlMapChangeAggregator:
    """Where all the urlMap change happens."""

    def __init__(self, url_map_name: str):
        self._map = {
            "name": url_map_name,
            "defaultService": GcpResourceManager.default_backend_service(),
            "hostRules": [],
            "pathMatchers": [],
        }

    def get_map(self) -> UrlMapType:
        return self._map

    def apply_change(self, test_case: 'XdsUrlMapTestCase') -> None:
        logging.info('Apply urlMap change for test case: %s.%s',
                     test_case.short_module_name, test_case.__name__)
        url_map_parts = test_case.url_map_change(
            *self._get_test_case_url_map(test_case))
        self._set_test_case_url_map(*url_map_parts)

    def _get_test_case_url_map(
            self,
            test_case: 'XdsUrlMapTestCase') -> Tuple[HostRule, PathMatcher]:
        host_rule = {
            "hosts": [test_case.hostname()],
            "pathMatcher": test_case.path_matcher_name(),
        }
        path_matcher = {
            "name": test_case.path_matcher_name(),
            "defaultService": GcpResourceManager.default_backend_service(),
        }
        return host_rule, path_matcher

    def _set_test_case_url_map(self, host_rule: HostRule,
                               path_matcher: PathMatcher) -> None:
        self._map["hostRules"].append(host_rule)
        self._map["pathMatchers"].append(path_matcher)


def _package_flags() -> Mapping[str, Any]:
    """Automatically parse Abseil flags into a dictionary.

    Abseil flag is only available after the Abseil app initialization. If we use
    __new__ in our metaclass, the flag value parse will happen during the
    initialization of modules, hence will fail. That's why we are using __call__
    to inject metaclass magics, and the flag parsing will be delayed until the
    class is about to be instantiated.
    """
    res = {}
    for flag_module in [xds_flags, xds_k8s_flags]:
        for key, value in inspect.getmembers(flag_module):
            if isinstance(value, flags.FlagHolder):
                res[key.lower()] = value.value
    res['strategy'] = STRATEGY.value
    return res


class _MetaSingletonAndAbslFlags(type):
    """Ensures singleton and injects flag values."""

    # Allow different subclasses to create different singletons.
    _instances = {}
    # But we only parse Abseil flags once.
    _flags = None

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            if cls._flags is None:
                cls._flags = _package_flags()
            obj = super().__call__(cls._flags, *args, **kwargs)
            cls._instances[cls] = obj
            return obj
        return cls._instances[cls]


class GcpResourceManager(metaclass=_MetaSingletonAndAbslFlags):
    """Manages the lifecycle of GCP resources.

    The GCP resources including:
        - 3 K8s deployment (client, default backends, alternative backends)
        - Full set of the Traffic Director stuff
        - Merged gigantic urlMap from all imported test cases

    All resources are intended to be used across test cases and multiple runs
    (except the client K8s deployment).
    """

    def __init__(self, absl_flags: Mapping[str, Any]):
        for key in absl_flags:
            setattr(self, key, absl_flags[key])
        # API managers
        self.k8s_api_manager = k8s.KubernetesApiManager(self.kube_context)
        self.gcp_api_manager = gcp.api.GcpApiManager()
        self.td = traffic_director.TrafficDirectorManager(
            self.gcp_api_manager,
            self.project,
            resource_prefix=self.namespace,
            network=self.network,
        )
        # Kubernetes namespace
        self.k8s_namespace = k8s.KubernetesNamespace(self.k8s_api_manager,
                                                     self.namespace)
        # Kubernetes Test Client
        self.test_client_runner = client_app.KubernetesClientRunner(
            self.k8s_namespace,
            deployment_name=self.client_name,
            image_name=self.client_image,
            gcp_project=self.project,
            gcp_api_manager=self.gcp_api_manager,
            gcp_service_account=self.gcp_service_account,
            td_bootstrap_image=self.td_bootstrap_image,
            network=self.network,
            debug_use_port_forwarding=self.debug_use_port_forwarding,
            stats_port=self.client_port,
            reuse_namespace=True)
        # Kubernetes Test Servers
        self.test_server_runner = server_app.KubernetesServerRunner(
            self.k8s_namespace,
            deployment_name=self.server_name,
            image_name=self.server_image,
            gcp_project=self.project,
            gcp_api_manager=self.gcp_api_manager,
            gcp_service_account=self.gcp_service_account,
            td_bootstrap_image=self.td_bootstrap_image,
            network=self.network)
        self.test_server_alternative_runner = server_app.KubernetesServerRunner(
            self.k8s_namespace,
            deployment_name=self.server_name + '-alternative',
            image_name=self.server_image,
            gcp_project=self.project,
            gcp_api_manager=self.gcp_api_manager,
            gcp_service_account=self.gcp_service_account,
            td_bootstrap_image=self.td_bootstrap_image,
            network=self.network,
            reuse_namespace=True)
        logging.info('Strategy of GCP resources management: %s', self.strategy)

    def setup(self, test_case_classes: 'Iterable[XdsUrlMapTestCase]') -> None:
        if self.strategy not in ['create', 'keep']:
            logging.info('GcpResourceManager: skipping setup for strategy [%s]',
                         self.strategy)
            return
        # Construct UrlMap from test classes
        # This is the step that mostly likely to go wrong. Lifting it to be the
        # first task ensures fail fast.
        aggregator = _UrlMapChangeAggregator(
            url_map_name="%s-%s" % (self.namespace, self.td.URL_MAP_NAME))
        for test_case_class in test_case_classes:
            aggregator.apply_change(test_case_class)
        final_url_map = aggregator.get_map()
        # Cleanup existing debris
        logging.info('GcpResourceManager: pre clean-up')
        self.td.cleanup(force=True)
        self.test_client_runner.delete_namespace()
        # Start creating GCP resources
        logging.info('GcpResourceManager: start setup')
        # Firewall
        if self.ensure_firewall:
            self.td.create_firewall_rule(
                allowed_ports=self.firewall_allowed_ports)
        # Health Checks
        self.td.create_health_check()
        # Backend Services
        self.td.create_backend_service()
        self.td.create_alternative_backend_service()
        # UrlMap
        self.td.create_url_map_with_content(final_url_map)
        # Target Proxy
        self.td.create_target_proxy()
        # Forwarding Rule
        self.td.create_forwarding_rule(self.server_xds_port)
        # Kubernetes Test Server
        self.test_server_runner.run(
            replica_count=1,
            test_port=self.server_port,
            maintenance_port=self.server_maintenance_port)
        # Kubernetes Test Server Alternative
        self.test_server_alternative_runner.run(
            replica_count=1,
            test_port=self.server_port,
            maintenance_port=self.server_maintenance_port)
        # Add backend to default backend service
        neg_name, neg_zones = self.k8s_namespace.get_service_neg(
            self.test_server_runner.service_name, self.server_port)
        self.td.backend_service_add_neg_backends(neg_name, neg_zones)
        # Add backend to alternative backend service
        neg_name, neg_zones = self.k8s_namespace.get_service_neg(
            self.test_server_alternative_runner.service_name, self.server_port)
        self.td.alternative_backend_service_add_neg_backends(
            neg_name, neg_zones)
        # Wait for healthy backends
        self.td.wait_for_backends_healthy_status()
        self.td.wait_for_alternative_backends_healthy_status()

    def tear_down(self) -> None:
        if self.strategy not in ['create']:
            logging.info(
                'GcpResourceManager: skipping tear down for strategy [%s]',
                self.strategy)
            return
        logging.info('GcpResourceManager: start tear down')
        if hasattr(self, 'td'):
            self.td.cleanup(force=True)
        if hasattr(self, 'test_client_runner'):
            self.test_client_runner.cleanup(force=True)
        if hasattr(self, 'test_server_runner'):
            self.test_server_runner.cleanup(force=True)
        if hasattr(self, 'test_server_alternative_runner'):
            self.test_server_alternative_runner.cleanup(force=True,
                                                        force_namespace=True)

    @staticmethod
    def default_backend_service() -> str:
        """Returns default backend service URL without GCP interaction."""
        # NOTE(lidiz) ideally, we should add an get_backend_service method to
        # TrafficDirectorManager, so we can fetch the URL in the most correct
        # way. However, the URL scheme won't change easily, and this is more
        # stable.
        return '%s/projects/%s/global/backendServices/%s-%s' % (
            _COMPUTE_V1_URL_PREFIX,
            xds_flags.PROJECT.value,
            xds_flags.NAMESPACE.value,
            traffic_director.TrafficDirectorManager.BACKEND_SERVICE_NAME,
        )

    @staticmethod
    def alternative_backend_service() -> str:
        """Returns alternative backend service URL without GCP interaction."""
        return '%s/projects/%s/global/backendServices/%s-%s' % (
            _COMPUTE_V1_URL_PREFIX,
            xds_flags.PROJECT.value,
            xds_flags.NAMESPACE.value,
            traffic_director.TrafficDirectorManager.
            ALTERNATIVE_BACKEND_SERVICE_NAME,
        )