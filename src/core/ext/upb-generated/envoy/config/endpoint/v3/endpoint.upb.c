/* This file was generated by upbc (the upb compiler) from the input
 * file:
 *
 *     envoy/config/endpoint/v3/endpoint.proto
 *
 * Do not edit -- your changes will be discarded when the file is
 * regenerated. */

#include <stddef.h>
#include "upb/msg.h"
#include "envoy/config/endpoint/v3/endpoint.upb.h"
#include "envoy/config/endpoint/v3/endpoint_components.upb.h"
#include "envoy/type/v3/percent.upb.h"
#include "google/api/annotations.upb.h"
#include "google/protobuf/duration.upb.h"
#include "google/protobuf/wrappers.upb.h"
#include "udpa/annotations/status.upb.h"
#include "udpa/annotations/versioning.upb.h"
#include "validate/validate.upb.h"

#include "upb/port_def.inc"

static const upb_msglayout *const envoy_config_endpoint_v3_ClusterLoadAssignment_submsgs[3] = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry_msginit,
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_msginit,
  &envoy_config_endpoint_v3_LocalityLbEndpoints_msginit,
};

static const upb_msglayout_field envoy_config_endpoint_v3_ClusterLoadAssignment__fields[4] = {
  {1, UPB_SIZE(4, 8), 0, 0, 9, 1},
  {2, UPB_SIZE(16, 32), 0, 2, 11, 3},
  {4, UPB_SIZE(12, 24), 1, 1, 11, 1},
  {5, UPB_SIZE(20, 40), 0, 0, 11, _UPB_LABEL_MAP},
};

const upb_msglayout envoy_config_endpoint_v3_ClusterLoadAssignment_msginit = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_submsgs[0],
  &envoy_config_endpoint_v3_ClusterLoadAssignment__fields[0],
  UPB_SIZE(24, 48), 4, false, 255,
};

static const upb_msglayout *const envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_submsgs[3] = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload_msginit,
  &google_protobuf_Duration_msginit,
  &google_protobuf_UInt32Value_msginit,
};

static const upb_msglayout_field envoy_config_endpoint_v3_ClusterLoadAssignment_Policy__fields[3] = {
  {2, UPB_SIZE(12, 24), 0, 0, 11, 3},
  {3, UPB_SIZE(4, 8), 1, 2, 11, 1},
  {4, UPB_SIZE(8, 16), 2, 1, 11, 1},
};

const upb_msglayout envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_msginit = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_submsgs[0],
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy__fields[0],
  UPB_SIZE(16, 32), 3, false, 255,
};

static const upb_msglayout *const envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload_submsgs[1] = {
  &envoy_type_v3_FractionalPercent_msginit,
};

static const upb_msglayout_field envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload__fields[2] = {
  {1, UPB_SIZE(4, 8), 0, 0, 9, 1},
  {2, UPB_SIZE(12, 24), 1, 0, 11, 1},
};

const upb_msglayout envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload_msginit = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload_submsgs[0],
  &envoy_config_endpoint_v3_ClusterLoadAssignment_Policy_DropOverload__fields[0],
  UPB_SIZE(16, 32), 2, false, 255,
};

static const upb_msglayout *const envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry_submsgs[1] = {
  &envoy_config_endpoint_v3_Endpoint_msginit,
};

static const upb_msglayout_field envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry__fields[2] = {
  {1, UPB_SIZE(0, 0), 0, 0, 9, 1},
  {2, UPB_SIZE(8, 16), 0, 0, 11, 1},
};

const upb_msglayout envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry_msginit = {
  &envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry_submsgs[0],
  &envoy_config_endpoint_v3_ClusterLoadAssignment_NamedEndpointsEntry__fields[0],
  UPB_SIZE(16, 32), 2, false, 255,
};

#include "upb/port_undef.inc"

