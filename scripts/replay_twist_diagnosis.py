#!/usr/bin/env python3
"""Replay recorded raw hand frames through the production retargeting session.

This is the offline regression seam for the twist layer: the recorded
``/rokoko/{side}/raw_hand`` frames are fed to a fresh ``RetargetingSession``
with the recorded configuration and the same Pinocchio/NLopt backends. The
resulting commands and twist snapshots are compared with the recorded
``/o10_control/{side}/command`` and ``/hand_retargeting/{side}/twist_state``.

No ROS node is started, no command is published and no hardware is touched.
Requires the numeric runtime (pinocchio, nlopt) and the version-locked model
fixture.

Usage:
    python3 scripts/replay_twist_diagnosis.py runs/twist-diag/<run> --side left
    python3 scripts/replay_twist_diagnosis.py <bag> --side left \
        --params runs/retargeting_diag_params.yaml --output replay_left.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

_ROOT = Path(__file__).resolve().parents[1]
for _candidate in (
    _ROOT / "src" / "hand_retargeting_node",
    _ROOT / "src" / "teleoperation_support" / "o10_contracts",
    _ROOT / "src" / "teleoperation_support" / "o10_model_assets",
):
    if _candidate.is_dir():
        sys.path.insert(0, str(_candidate))

from hand_retargeting.adapters.model_geometry import (  # noqa: E402
    load_robot_geometry,
    load_runtime_assets,
)
from hand_retargeting.adapters.nlopt import NloptSlsqpOptimizer  # noqa: E402
from hand_retargeting.adapters.pinocchio import load_pinocchio_kinematics  # noqa: E402
from hand_retargeting.application.session import RetargetingSession  # noqa: E402
from hand_retargeting.contracts import (  # noqa: E402
    RawHandFrameValue,
    RetargetingConfig,
    TwistConfig,
)
from hand_retargeting.core.coupling import CouplingModel  # noqa: E402

# These names must match ``TwistSnapshot`` in the pure layer (hyphenated).
_STATUS_NAMES = {
    0: "not-active",
    1: "applied",
    2: "fallback-baseline",
}
_FAILURE_NAMES = {
    0: "none",
    1: "robot-reference-invalid",
    2: "human-reference-invalid",
    3: "human-geometry-invalid",
    4: "backend-unavailable",
    5: "solver-error",
    6: "nonfinite",
    7: "limits",
    8: "trust-region",
    9: "degenerate-tripod",
    10: "axis-deviation",
    11: "baseline-incomplete",
    12: "refinement-rejected",
    13: "axis-mismatch",
}


def _stamp_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _load_yaml_params(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root = data.get("/**", data)
    params = root.get("ros__parameters", root)
    if not isinstance(params, dict):
        raise SystemExit(f"cannot find ros__parameters in {path}")
    return params


def _twist_from_params(params: dict) -> TwistConfig:
    names = (
        "gate_aperture_on",
        "gate_aperture_off",
        "gate_extension_min",
        "gate_on_frames",
        "gate_off_frames",
        "weight_rot",
        "weight_conn",
        "weight_axis",
        "weight_pos",
        "iterations",
        "step_max",
        "trust_region",
        "delta_theta_clip",
        "gradient_tolerance",
        "axis_epsilon",
        "projection_epsilon",
        "axis_deviation_limit_deg",
    )
    missing = [name for name in names if f"twist_{name}" not in params]
    if missing:
        raise SystemExit(
            "params file is missing twist keys: "
            + ", ".join(f"twist_{name}" for name in missing)
        )
    return TwistConfig(
        **{name: params[f"twist_{name}"] for name in names}
    )


def _config_from_params(params: dict) -> RetargetingConfig:
    required = (
        "palm_y_epsilon",
        "palm_x_epsilon",
        "finger_length_epsilon",
        "length_window_size",
        "stable_window_count",
        "length_nmad_thresholds",
        "frozen_length_relative_thresholds",
        "ik_residual_thresholds",
        "ik_max_evaluations",
        "ik_max_time_sec",
        "smooth_time_constants",
        "stale_timeout_sec",
        "recovery_min_valid_frames",
        "recovery_min_duration_sec",
        "thumb_roll_sensitivity",
    )
    missing = [name for name in required if name not in params]
    if missing:
        raise SystemExit("params file is missing keys: " + ", ".join(missing))
    return RetargetingConfig(
        **{name: params[name] for name in required},
        recovery_confirmation_timeout_sec=params.get(
            "recovery_confirmation_timeout_sec", 0.5
        ),
        thumb_abad_sensitivity=params.get("thumb_abad_sensitivity", 1.0),
        thumb_roll_fixed_value=params.get("thumb_roll_fixed_value"),
        thumb_abad_fixed_value=params.get("thumb_abad_fixed_value"),
        twist=_twist_from_params(params),
    )


def _build_session(side: str, config: RetargetingConfig) -> RetargetingSession:
    geometry = load_robot_geometry(side)
    assets = load_runtime_assets(side)
    kinematics = load_pinocchio_kinematics(assets, side)
    coupling = CouplingModel.from_mjcf(assets.coupling_model)
    optimizer = NloptSlsqpOptimizer(
        coupling, kinematics, config.ik_max_evaluations, config.ik_max_time_sec
    )
    return RetargetingSession(
        side,
        config,
        geometry,
        coupling=coupling,
        kinematics=kinematics,
        optimizer=optimizer,
    )


def _read_bag(bag_path: Path, side: str):
    try:
        from rclpy.serialization import deserialize_message
        from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
        from rokoko_omnihand_msgs.msg import RawHandFrame, TwistState
        from sensor_msgs.msg import JointState
    except ImportError as error:  # pragma: no cover - environment gate
        raise SystemExit(
            "replay requires the ROS environment (rosbag2_py, generated msgs)"
        ) from error

    raw_topic = f"/rokoko/{side}/raw_hand"
    twist_topic = f"/hand_retargeting/{side}/twist_state"
    command_topic = f"/o10_control/{side}/command"

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag_path), storage_id="mcap"),
        ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    raw_frames = []
    twist_states = []
    commands = []
    while reader.has_next():
        name, data, _timestamp = reader.read_next()
        if name == raw_topic:
            message = deserialize_message(data, RawHandFrame)
            raw_frames.append(
                RawHandFrameValue(
                    node_names=tuple(message.node_names),
                    positions=tuple(
                        (point.x, point.y, point.z)
                        for point in message.positions
                    ),
                    received_at_ns=_stamp_ns(message.header.stamp),
                )
            )
        elif name == twist_topic:
            twist_states.append(deserialize_message(data, TwistState))
        elif name == command_topic:
            commands.append(deserialize_message(data, JointState))
    return raw_frames, twist_states, commands


def _resolve_bag(path: Path) -> Path:
    return path / "bag" if (path / "bag").is_dir() else path


def _max_abs(values) -> float | None:
    finite = [abs(value) for value in values if math.isfinite(value)]
    return max(finite) if finite else None


def _mean_abs(values) -> float | None:
    finite = [abs(value) for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def _compare_commands(replayed, recorded) -> dict:
    by_stamp = {}
    for message in recorded:
        by_stamp.setdefault(_stamp_ns(message.header.stamp), message)
    differences = []
    matched = 0
    for stamp_ns, positions, _decision in replayed:
        message = by_stamp.get(stamp_ns)
        if message is None or len(message.position) != len(positions):
            continue
        matched += 1
        differences.extend(
            float(left) - float(right)
            for left, right in zip(positions, message.position)
        )
    return {
        "matched_frames": matched,
        "replayed_frames": len(replayed),
        "recorded_frames": len(recorded),
        "max_abs_diff": _max_abs(differences),
        "mean_abs_diff": _mean_abs(differences),
    }


def _compare_twist(replayed, recorded) -> dict:
    """Compare snapshots by sequence; TwistState stamp is publish time."""
    pairs = []
    for (_stamp_ns_value, _positions, decision), message in zip(
        replayed, recorded
    ):
        if decision.twist is None:
            continue
        pairs.append((decision.twist, message))
    fields = {
        "theta_task": lambda snapshot, message: snapshot.theta_task - message.theta_task,
        "theta_base": lambda snapshot, message: snapshot.theta_base - message.theta_base,
        "theta_increment": (
            lambda snapshot, message: snapshot.theta_increment - message.theta_increment
        ),
        "gate_aperture": (
            lambda snapshot, message: snapshot.gate_aperture - message.gate_aperture
        ),
        "gate_extension": (
            lambda snapshot, message: snapshot.gate_extension - message.gate_extension
        ),
        "objective_total": (
            lambda snapshot, message: snapshot.objective_total - message.objective_total
        ),
    }
    result = {
        "matched_frames": len(pairs),
        "replayed_frames": len(replayed),
        "recorded_frames": len(recorded),
        "active_mismatches": sum(
            1
            for snapshot, message in pairs
            if bool(snapshot.active) != bool(message.active)
        ),
        "status_mismatches": sum(
            1
            for snapshot, message in pairs
            if snapshot.refinement_status
            != _STATUS_NAMES.get(int(message.refinement_status), "unknown")
        ),
        "failure_mismatches": sum(
            1
            for snapshot, message in pairs
            if (snapshot.failure_reason or "none")
            != _FAILURE_NAMES.get(int(message.failure_reason), "unknown")
        ),
    }
    for name, difference in fields.items():
        values = [difference(snapshot, message) for snapshot, message in pairs]
        result[name] = {
            "max_abs_diff": _max_abs(values),
            "mean_abs_diff": _mean_abs(values),
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", help="twist-diag run directory or bag directory")
    parser.add_argument("--side", default="left", choices=("left", "right"))
    parser.add_argument(
        "--params",
        default=None,
        help="parameter snapshot (default: <run>/retargeting_diag_params.yaml)",
    )
    parser.add_argument(
        "--output", default=None, help="replay JSON destination"
    )
    arguments = parser.parse_args(argv)

    run_path = Path(arguments.run).expanduser().resolve()
    bag_path = _resolve_bag(run_path)
    params_path = (
        Path(arguments.params).expanduser()
        if arguments.params
        else run_path / "retargeting_diag_params.yaml"
    )
    if not params_path.is_file():
        params_path = _ROOT / "runs" / "retargeting_diag_params.yaml"
    config = _config_from_params(_load_yaml_params(params_path))
    session = _build_session(arguments.side, config)
    raw_frames, twist_states, commands = _read_bag(bag_path, arguments.side)
    if not raw_frames:
        raise SystemExit(f"no raw_hand frames for {arguments.side} in {bag_path}")

    replayed = []
    started = time.perf_counter()
    for frame in raw_frames:
        decision = session.process(frame)
        replayed.append(
            (
                frame.received_at_ns,
                decision.command_positions or (),
                decision,
            )
        )
    elapsed = time.perf_counter() - started

    command_comparison = _compare_commands(replayed, commands)
    twist_comparison = _compare_twist(replayed, twist_states)
    summary = {
        "side": arguments.side,
        "bag": str(bag_path),
        "params": str(params_path),
        "raw_frames": len(raw_frames),
        "replay_elapsed_sec": elapsed,
        "command": command_comparison,
        "twist": twist_comparison,
        "object_rotation_measured": False,
        "object_rotation_note": (
            "物体实际转角未测。回放只验证重定向会话的命令与诊断可复现性。"
        ),
    }
    output = (
        Path(arguments.output).expanduser()
        if arguments.output
        else (run_path / f"replay_{arguments.side}.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    print(f"[twist-replay] {output}")
    print(
        "[twist-replay] command max_abs_diff="
        f"{command_comparison['max_abs_diff']} matched={command_comparison['matched_frames']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
