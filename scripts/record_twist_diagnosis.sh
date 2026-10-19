#!/usr/bin/env bash
# Independent DexTwist diagnostic recorder.
#
# This script is deliberately outside the retargeting node and outside the
# data-collection MCAP path. It records the complete twist observation chain to
# runs/twist-diag/<timestamp>/ so the layer can be analysed and replayed:
#   - human input:        /rokoko/{side}/raw_hand
#   - gate/refinement:    /hand_retargeting/{side}/twist_state
#   - baseline decisions: /hand_retargeting/{side}/state
#   - soft command:       /o10_control/{side}/command
#   - final command:      /o10/{side}/joint_cmd
#   - hardware feedback:  /o10/{side}/joint_states
#   - control decision:   /o10_control/{side}/state
#
# The canonical launcher starts this script before the business nodes and
# stops it with the rest of the graph. It never publishes, never calls a
# Service and never writes the collection dataset.
#
# Usage:
#   ./record_twist_diagnosis.sh [options]
#
# Options:
#   --side left|right|both   Sides to record (default: left)
#   --config PATH            Retargeting parameter snapshot to copy
#   --output-dir PATH        Explicit run directory (default timestamped)
#   --max-duration SEC       Stop recording after SEC seconds (default 1800)
#   --min-free-gb GB         Stop if the filesystem drops below GB (default 1)
#   --dry-run                Print the complete plan without recording
#   -h, --help               Show this help
#
# Ctrl-C/SIGTERM stops the rosbag2 process with SIGINT so the MCAP is closed.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
DEFAULT_CONFIG="$ROOT_DIR/runs/retargeting_diag_params.yaml"
DEFAULT_OUTPUT_ROOT="$ROOT_DIR/runs/twist-diag"

SIDES="left"
CONFIG_PATH="$DEFAULT_CONFIG"
OUTPUT_DIR=""
MAX_DURATION_SEC=1800
MIN_FREE_GB=1
DRY_RUN=0

usage() {
  sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

die() { echo "[twist-record][FAIL] $*" >&2; exit 1; }
info() { echo "[twist-record] $*"; }
warn() { echo "[twist-record][WARN] $*" >&2; }

while (($# > 0)); do
  case "$1" in
    --side)
      [[ $# -ge 2 ]] || die "--side requires left|right|both"
      SIDES="$2"
      shift
      ;;
    --side=*) SIDES="${1#*=}" ;;
    --config)
      [[ $# -ge 2 ]] || die "--config requires a path"
      CONFIG_PATH="$2"
      shift
      ;;
    --config=*) CONFIG_PATH="${1#*=}" ;;
    --output-dir)
      [[ $# -ge 2 ]] || die "--output-dir requires a path"
      OUTPUT_DIR="$2"
      shift
      ;;
    --output-dir=*) OUTPUT_DIR="${1#*=}" ;;
    --max-duration)
      [[ $# -ge 2 ]] || die "--max-duration requires seconds"
      MAX_DURATION_SEC="$2"
      shift
      ;;
    --max-duration=*) MAX_DURATION_SEC="${1#*=}" ;;
    --min-free-gb)
      [[ $# -ge 2 ]] || die "--min-free-gb requires a value"
      MIN_FREE_GB="$2"
      shift
      ;;
    --min-free-gb=*) MIN_FREE_GB="${1#*=}" ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
  shift
done

case "$SIDES" in
  left|right|both) ;;
  *) die "invalid --side value: '$SIDES' (expected left|right|both)" ;;
esac
[[ "$MAX_DURATION_SEC" =~ ^[1-9][0-9]*$ ]] \
  || die "--max-duration must be a positive integer"
[[ "$MIN_FREE_GB" =~ ^[0-9]+([.][0-9]+)?$ ]] \
  || die "--min-free-gb must be a non-negative number"
[[ -f "$CONFIG_PATH" ]] || die "missing retargeting parameter snapshot: $CONFIG_PATH"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -z "$OUTPUT_DIR" ]]; then
  # The PID suffix keeps two recorders started in the same wall-clock second
  # from colliding on the same run directory.
  OUTPUT_DIR="$DEFAULT_OUTPUT_ROOT/${STAMP}-$$"
fi
BAG_DIR="$OUTPUT_DIR/bag"
QOS_FILE="$OUTPUT_DIR/qos_overrides.yaml"
TOPICS_FILE="$OUTPUT_DIR/topics.txt"
README_FILE="$OUTPUT_DIR/README.md"
META_FILE="$OUTPUT_DIR/metadata.json"
RECORD_LOG="$OUTPUT_DIR/record.log"
CONFIG_SNAPSHOT="$OUTPUT_DIR/retargeting_diag_params.yaml"

declare -a SIDE_LIST=()
case "$SIDES" in
  left) SIDE_LIST=(left) ;;
  right) SIDE_LIST=(right) ;;
  both) SIDE_LIST=(left right) ;;
esac

declare -a TOPICS=()
for side in "${SIDE_LIST[@]}"; do
  TOPICS+=(
    "/hand_retargeting/$side/twist_state"
    "/rokoko/$side/raw_hand"
    "/hand_retargeting/$side/state"
    "/o10_control/$side/command"
    "/o10/$side/joint_cmd"
    "/o10/$side/joint_states"
    "/o10_control/$side/state"
  )
done

write_qos_overrides() {
  : >"$QOS_FILE"
  for topic in "${TOPICS[@]}"; do
    cat >>"$QOS_FILE" <<EOF
$topic:
  reliability: best_effort
  durability: volatile
  history: keep_last
  depth: 10
EOF
  done
}

write_readme() {
  cat >"$README_FILE" <<EOF
# DexTwist diagnostic recording

- Run directory: \`$OUTPUT_DIR\`
- Sides: \`$SIDES\`
- Created (UTC): \`$STAMP\`
- Config snapshot: \`$CONFIG_SNAPSHOT\`
- MCAP bag: \`$BAG_DIR\`
- Topics: \`$TOPICS_FILE\`
- QoS overrides: \`$QOS_FILE\`
- Recording log: \`$RECORD_LOG\`
- Metadata: \`$META_FILE\`

## What this is

A **read-only diagnostic recording** of the twist layer. It is separate from the
data-collection MCAP dataset and must not be merged into it.

The recording covers the human input frame, the tripod gate and accumulated
angle, the refinement result, the soft command, the final O10 command, the O10
feedback and the O10 control state. Time alignment in the analysis tool uses the
ROS message \`header.stamp\`; see \`scripts/analyze_twist_diagnosis.py\`.

## Explicit limitation

The object's actual rotation is **not measured**. This recording can only
support "robot joint angle vs human intent" and axis-deviation acceptance. It
cannot prove that the object was turned or that the contact did not slip.
EOF
}

write_metadata() {
  local phase="$1"
  local git_commit git_status free_kb
  git_commit="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  git_status="$(git -C "$ROOT_DIR" status --porcelain 2>/dev/null | head -200 || true)"
  free_kb="$(df -Pk "$OUTPUT_DIR" | awk 'NR==2 {print $4}')"
  {
    printf '{\n'
    printf '  "phase": "%s",\n' "$phase"
    printf '  "created_utc": "%s",\n' "$STAMP"
    printf '  "sides": "%s",\n' "$SIDES"
    printf '  "git_commit": "%s",\n' "$git_commit"
    printf '  "git_status_head": "%s",\n' "$(printf '%s' "$git_status" | head -1 | sed 's/"/\\"/g')"
    printf '  "config_snapshot": "%s",\n' "$CONFIG_SNAPSHOT"
    printf '  "bag_dir": "%s",\n' "$BAG_DIR"
    printf '  "max_duration_sec": %s,\n' "$MAX_DURATION_SEC"
    printf '  "min_free_gb": %s,\n' "$MIN_FREE_GB"
    printf '  "free_kb_at_%s": %s,\n' "$phase" "${free_kb:-0}"
    printf '  "object_rotation_measured": false\n'
    printf '}\n'
  } >"$META_FILE"
}

record_command() {
  printf 'ros2 bag record -s mcap -o %q --qos-profile-overrides-path %q' \
    "$BAG_DIR" "$QOS_FILE"
  printf ' %q' "${TOPICS[@]}"
  printf '\n'
}

plan() {
  info "Run directory: $OUTPUT_DIR"
  info "Bag directory: $BAG_DIR"
  info "Config snapshot: $CONFIG_PATH -> $CONFIG_SNAPSHOT"
  info "Sides: $SIDES"
  info "Topics:"
  printf '  %s\n' "${TOPICS[@]}"
  info "QoS overrides: $QOS_FILE (best_effort/volatile/keep_last(10))"
  info "Max duration: ${MAX_DURATION_SEC}s; min free space: ${MIN_FREE_GB} GiB"
  info "Command:"
  record_command
  info "Metadata: $META_FILE"
  info "README: $README_FILE"
}

if ((DRY_RUN)); then
  info "DRY RUN: no files created, no ROS processes started."
  plan
  exit 0
fi

[[ -f "$ROOT_DIR/AGENTS.md" ]] || die "not the ROTRAC repository root: $ROOT_DIR"
mkdir -p "$OUTPUT_DIR"
if [[ -e "$BAG_DIR" ]]; then
  die "bag directory already exists: $BAG_DIR"
fi
if (( $(df -Pk "$OUTPUT_DIR" | awk 'NR==2 {print $4}') < $(awk -v gb="$MIN_FREE_GB" 'BEGIN {printf "%d", gb*1024*1024}') )); then
  die "insufficient free space for $OUTPUT_DIR (need ${MIN_FREE_GB} GiB)"
fi

write_qos_overrides
printf '%s\n' "${TOPICS[@]}" >"$TOPICS_FILE"
cp -- "$CONFIG_PATH" "$CONFIG_SNAPSHOT"
write_readme
write_metadata "starting"
plan

# Match the production graph environment. This process is standalone, so
# sourcing ROS here does not affect the canonical launcher.
set +u
source /opt/ros/jazzy/setup.bash
if [[ -f "$ROOT_DIR/scripts/workspace_paths.sh" ]]; then
  # shellcheck source=workspace_paths.sh
  source "$ROOT_DIR/scripts/workspace_paths.sh"
  if [[ -f "$ROTRAC_INSTALL_BASE/setup.bash" ]]; then
    source "$ROTRAC_INSTALL_BASE/setup.bash"
  fi
fi
set -u
command -v ros2 >/dev/null || die "ros2 is not available"

BAG_PID=""
STOP_REASON=""
stop_bag() {
  local reason="${1:-signal}"
  local attempt
  STOP_REASON="$reason"
  if [[ -n "$BAG_PID" ]] && kill -0 "$BAG_PID" 2>/dev/null; then
    # ros2bag installs a SIGTERM handler that stops the Recorder and closes the
    # MCAP; its SIGINT path depends on an interactive KeyboardInterrupt and is
    # unreliable for a daemonized child. SIGTERM is therefore the graceful
    # signal here. Escalate only if the process refuses to leave.
    kill -TERM -- "-$BAG_PID" 2>/dev/null || kill -TERM "$BAG_PID" 2>/dev/null || true
    for attempt in $(seq 1 20); do
      kill -0 "$BAG_PID" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$BAG_PID" 2>/dev/null; then
      warn "rosbag2 did not stop after SIGTERM; escalating to SIGKILL"
      kill -KILL -- "-$BAG_PID" 2>/dev/null || kill -KILL "$BAG_PID" 2>/dev/null || true
    fi
    wait "$BAG_PID" 2>/dev/null || true
  fi
  BAG_PID=""
}

finish() {
  local status=$?
  if [[ -n "$BAG_PID" ]]; then
    stop_bag "exit"
  fi
  write_metadata "finished"
  rm -f -- "${BAG_PID_FILE:-}"
  info "Recording finished (status=$status, reason=${STOP_REASON:-bag-exited})."
  info "Run directory: $OUTPUT_DIR"
  info "MCAP: $BAG_DIR"
  exit "$status"
}
trap finish EXIT
trap 'stop_bag "signal"; exit 130' INT TERM HUP

info "Starting rosbag2 MCAP recording."
# ``setsid`` normally forks, so ``$!`` is the wrapper rather than rosbag2. The
# child writes its own PID before exec: that PID is the one to signal, and
# ``trap - INT`` restores SIGINT after the shell marked the background job as
# ignoring it.
BAG_PID_FILE="$OUTPUT_DIR/bag.pid"
rm -f -- "$BAG_PID_FILE"
setsid bash -c 'echo $$ > "$1"; trap - INT; shift; exec "$@"' \
  _ "$BAG_PID_FILE" ros2 bag record -s mcap -o "$BAG_DIR" \
  --qos-profile-overrides-path "$QOS_FILE" \
  "${TOPICS[@]}" >>"$RECORD_LOG" 2>&1 &
WRAPPER_PID=$!
for _ in $(seq 1 50); do
  [[ -s "$BAG_PID_FILE" ]] && break
  sleep 0.1
done
if [[ -s "$BAG_PID_FILE" ]]; then
  BAG_PID="$(cat "$BAG_PID_FILE")"
else
  warn "rosbag2 did not publish a PID file; falling back to the wrapper PID"
  BAG_PID="$WRAPPER_PID"
fi
sleep 1
kill -0 "$BAG_PID" 2>/dev/null || die "rosbag2 exited immediately; inspect $RECORD_LOG"
write_metadata "recording"

STARTED_AT="$SECONDS"
while kill -0 "$BAG_PID" 2>/dev/null; do
  elapsed=$((SECONDS - STARTED_AT))
  if ((elapsed >= MAX_DURATION_SEC)); then
    stop_bag "max-duration"
    break
  fi
  free_kb="$(df -Pk "$OUTPUT_DIR" | awk 'NR==2 {print $4}')"
  min_kb="$(awk -v gb="$MIN_FREE_GB" 'BEGIN {printf "%d", gb*1024*1024}')"
  if ((free_kb < min_kb)); then
    warn "free space ${free_kb}KiB below ${min_kb}KiB; stopping recording"
    stop_bag "low-disk"
    break
  fi
  sleep 1
done
stop_bag "${STOP_REASON:-bag-exited}"
