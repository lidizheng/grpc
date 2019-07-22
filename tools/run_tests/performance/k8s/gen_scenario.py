from __future__ import print_function

import os
import json
import sys
sys.path.append(os.path.join(os.getcwd(), 'tools', 'run_tests'))
from performance import scenario_config

def scenario_filter(scenario):
    return scenario["name"] == 'cpp_protobuf_async_unary_ping_pong_insecure'

print(json.dumps(
    filter(scenario_filter, scenario_config.CXXLanguage().scenarios())
))
