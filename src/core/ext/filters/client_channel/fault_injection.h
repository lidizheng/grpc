//
//
// Copyright 2020 gRPC authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
//

#ifndef GRPC_CORE_EXT_FILTERS_CLIENT_CHANNEL_FAULT_INJECTION_H
#define GRPC_CORE_EXT_FILTERS_CLIENT_CHANNEL_FAULT_INJECTION_H

#include <grpc/support/port_platform.h>

#include "src/core/ext/filters/client_channel/resolver_result_parsing.h"
#include "src/core/lib/gprpp/arena.h"
#include "src/core/lib/iomgr/timer.h"
#include "src/core/lib/transport/metadata_batch.h"

namespace grpc_core {
namespace internal {

// FaultInjectionData contains configs for fault injection enforcement.
// Its scope is per-call and it should share the lifespan of the attaching call.
// This class will be used to:
//   1. Update FI configs from other sources;
//   2. Roll the fault-injection dice;
//   3. Maintain the counter of active faults.
class FaultInjectionData {
 public:
  static FaultInjectionData* MaybeCreateFaultInjectionData(
      const ClientChannelMethodParsedConfig::FaultInjectionPolicy* fi_policy,
      grpc_metadata_batch* initial_metadata, Arena* arena);

  FaultInjectionData();
  ~FaultInjectionData();

  bool MaybeAbort();
  bool MaybeDelay();

  grpc_error* GetAbortError();
  void ScheduleNextPick(grpc_closure* closure);

 private:
  // Modifies internal states to when fault injection actually starts, also
  // checks if current active faults exceed the allowed max faults.
  bool BeginFaultInjection();
  // EndFaultInjection maybe called multiple time to stop the fault injection.
  bool EndFaultInjection();
  bool active_fault_increased_ = false;
  bool active_fault_decreased_ = false;
  // Flag if each fault injection is enabled
  bool abort_request_ = false;
  bool delay_request_ = false;
  bool rate_limit_response_ = false;
  // Delay statuses
  bool delay_injected_ = false;
  bool delay_finished_ = false;
  grpc_timer delay_timer_;
  grpc_millis pick_again_time_;
  // Abort status
  bool abort_injected_ = false;
  bool abort_finished_ = false;
  const ClientChannelMethodParsedConfig::FaultInjectionPolicy* fi_policy_;
};

}  // namespace internal
}  // namespace grpc_core

#endif /* GRPC_CORE_EXT_FILTERS_CLIENT_CHANNEL_FAULT_INJECTION_H */
