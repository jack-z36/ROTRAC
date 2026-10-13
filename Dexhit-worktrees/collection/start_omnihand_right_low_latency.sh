#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

OMNIHAND_O10_RIGHT_CANFD_DEVICE_ID=0 \
exec ./start_omnihand_control.sh --sides right --tactile-rate 30 \
  --param executor_threads=1 \
  --param right.control_check_period=0.2 \
  --param right.command_best_effort=true \
  --param right.target_best_effort=true \
  --param right.command_link_best_effort=true \
  --param right.latest_target_send_period=0.016666667 \
  --param right.state_publish_min_period=0.2 \
  --param right.metrics_log_period=2.0 \
  --param thumb_roll_fixed_value=0.5458517235612265 \
  --param o10.right.command_best_effort=true \
  --param o10.right.request_interval_ms=0 \
  --param o10.right.feedback_read_period=0.016666667 \
  --param right.error_poll_period=30.0
