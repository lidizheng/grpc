from __future__ import print_function

import os
import json
import sys
sys.path.append(os.path.join(os.getcwd(), 'tools', 'run_tests'))
from performance import scenario_config

def scenario_filter(scenario):
    return scenario["name"] == 'cpp_protobuf_async_unary_ping_pong_insecure'

scenarios = filter(scenario_filter, scenario_config.CXXLanguage().scenarios())
cleaned_scenarios = map(scenario_config.remove_nonproto_fields, scenarios)
print(json.dumps(
    dict(
        scenarios=cleaned_scenarios,
    )
))
