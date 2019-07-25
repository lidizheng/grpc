from __future__ import print_function

import os
import json
import sys
sys.path.append(os.path.join(os.getcwd(), 'tools', 'run_tests'))
from performance import scenario_config

def scenario_filter(scenario):
    # return scenario["name"] == 'cpp_protobuf_async_streaming_from_server_qps_unconstrained_insecure_100_channels_100_outstanding'
    return scenario["name"] == 'cpp_protobuf_async_unary_qps_unconstrained_secure_1b'

scenarios = filter(scenario_filter, scenario_config.CXXLanguage().scenarios())
cleaned_scenarios = map(scenario_config.remove_nonproto_fields, scenarios)
print(json.dumps(
    dict(
        scenarios=cleaned_scenarios,
    )
))
