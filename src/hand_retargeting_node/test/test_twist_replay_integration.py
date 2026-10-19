"""Opt-in end-to-end replay check on a synthetic MCAP recording.

This test needs the version-locked model fixture plus pinocchio and nlopt. It
runs the production session twice: once to synthesize a recording, then again
through ``scripts/replay_twist_diagnosis.py`` on the recorded raw frames. The
recorded commands and TwistState fields must reproduce within floating-point
tolerance.

It does not touch hardware, UDP, ROS nodes or the live graph.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

from hand_retargeting.contracts import RawHandFrameValue
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "replay_twist_diagnosis.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "replay_twist_diagnosis_integration", _SCRIPT_PATH
)
replay = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = replay
_SPEC.loader.exec_module(replay)

_REAL_ASSETS = (
    bool(os.environ.get("OMNIHAND_O10_MODEL_FIXTURE"))
    and importlib.util.find_spec("pinocchio") is not None
    and importlib.util.find_spec("nlopt") is not None
    and importlib.util.find_spec("rosbag2_py") is not None
)

pytestmark = pytest.mark.skipif(
    not _REAL_ASSETS,
    reason="requires OMNIHAND_O10_MODEL_FIXTURE, pinocchio, nlopt and rosbag2_py",
)

_NODE_SUFFIXES = (
    "Hand",
    "ThumbProximal", "ThumbMedial", "ThumbDistal", "ThumbTip",
    "IndexProximal", "IndexMedial", "IndexDistal", "IndexTip",
    "MiddleProximal", "MiddleMedial", "MiddleDistal", "MiddleTip",
    "RingProximal", "RingMedial", "RingDistal", "RingTip",
    "LittleProximal", "LittleMedial", "LittleDistal", "LittleTip",
)

_STATUS_TO_ENUM = {
    "not-active": 0,
    "applied": 1,
    "fallback-baseline": 2,
}
_FAILURE_TO_ENUM = {
    "none": 0,
    "robot_reference_invalid": 1,
    "human_reference_invalid": 2,
    "human_geometry_invalid": 3,
    "backend_unavailable": 4,
    "solver_error": 5,
    "nonfinite": 6,
    "limits": 7,
    "trust_region": 8,
    "degenerate_tripod": 9,
    "axis_deviation": 10,
    "baseline_incomplete": 11,
    "refinement_rejected": 12,
    "axis_mismatch": 13,
}


def _positions():
    positions = [(0.0, 0.0, 0.0)]
    for root in (0.8, 0.6, 0.2, -0.2, -0.6):
        positions.extend(
            [(root, 1.0, 0.0), (root, 1.4, 0.0), (root, 1.8, 0.0), (root, 2.2, 0.0)]
        )
    positions[4] = (0.4, 2.0, 0.2)
    return positions


def _params_dict():
    import yaml

    root = Path(__file__).resolve().parents[3]
    data = yaml.safe_load(
        (root / "runs" / "retargeting_diag_params.yaml").read_text(
            encoding="utf-8"
        )
    )
    params = data["/**"]["ros__parameters"]
    # Synthetic human geometry is not the calibrated operator geometry. Raise
    # the baseline residual gate so the test exercises the twist path instead
    # of stopping at baseline IK residuals.
    params["ik_residual_thresholds"] = [100.0] * 5
    params["smooth_time_constants"] = [0.005] * 10
    return params


def _frame(stamp_ns):
    return RawHandFrameValue(
        tuple("left" + suffix for suffix in _NODE_SUFFIXES),
        tuple(_positions()),
        stamp_ns,
    )


def test_synthetic_recording_replays_to_the_same_commands_and_twist_state():
    from geometry_msgs.msg import Point
    from rclpy.serialization import serialize_message
    from rokoko_omnihand_msgs.msg import RawHandFrame, TwistState
    from rosbag2_py import (
        ConverterOptions,
        SequentialWriter,
        StorageOptions,
        TopicMetadata,
    )
    from sensor_msgs.msg import JointState

    params = _params_dict()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        params_path = root / "params.yaml"
        import yaml

        params_path.write_text(
            yaml.safe_dump({"/**": {"ros__parameters": params}}),
            encoding="utf-8",
        )
        config = replay._config_from_params(params)
        session = replay._build_session("left", config)

        bag = root / "bag"
        writer = SequentialWriter()
        writer.open(
            StorageOptions(uri=str(bag), storage_id="mcap"),
            ConverterOptions(
                input_serialization_format="cdr",
                output_serialization_format="cdr",
            ),
        )
        raw_topic = "/rokoko/left/raw_hand"
        command_topic = "/o10_control/left/command"
        twist_topic = "/hand_retargeting/left/twist_state"
        for index, name in enumerate(
            (raw_topic, command_topic, twist_topic)
        ):
            message_type = (
                "rokoko_omnihand_msgs/msg/RawHandFrame"
                if name == raw_topic
                else "sensor_msgs/msg/JointState"
                if name == command_topic
                else "rokoko_omnihand_msgs/msg/TwistState"
            )
            writer.create_topic(TopicMetadata(index, name, message_type, "cdr"))

        from omnihand_o10_contracts import ACTIVE_JOINT_NAMES

        base_ns = 1_000_000_000
        for index in range(20):
            stamp_ns = base_ns + index * 100_000_000
            frame = _frame(stamp_ns)
            decision = session.process(frame)

            raw = RawHandFrame()
            raw.header.stamp.sec = stamp_ns // 1_000_000_000
            raw.header.stamp.nanosec = stamp_ns % 1_000_000_000
            raw.node_names = list(frame.node_names)
            raw.positions = [Point(x=x, y=y, z=z) for x, y, z in frame.positions]
            writer.write(raw_topic, serialize_message(raw), stamp_ns)

            if decision.command_positions is not None:
                command = JointState()
                command.header.stamp = raw.header.stamp
                command.name = list(ACTIVE_JOINT_NAMES)
                command.position = list(decision.command_positions)
                writer.write(
                    command_topic, serialize_message(command), stamp_ns
                )

            snapshot = decision.twist
            if snapshot is not None:
                twist = TwistState()
                twist.header.stamp = raw.header.stamp
                twist.side = "left"
                twist.valid = bool(snapshot.valid)
                twist.active = bool(snapshot.active)
                twist.gate_aperture = float(snapshot.gate_aperture)
                twist.gate_extension = float(snapshot.gate_extension)
                twist.theta_task = float(snapshot.theta_task)
                twist.theta_base = float(snapshot.theta_base)
                twist.theta_increment = float(snapshot.theta_increment)
                twist.theta_robot_cmd = float(snapshot.theta_robot_cmd)
                twist.theta_robot_fb = float(snapshot.theta_robot_fb)
                twist.theta_robot_fb_available = bool(
                    snapshot.theta_robot_fb_available
                )
                twist.axis_deviation_cmd_deg = float(
                    snapshot.axis_deviation_cmd_deg
                )
                twist.axis_deviation_fb_deg = float(
                    snapshot.axis_deviation_fb_deg
                )
                twist.axis_deviation_fb_available = bool(
                    snapshot.axis_deviation_fb_available
                )
                twist.objective_total = float(snapshot.objective_total)
                twist.objective_rot = float(snapshot.objective_rot)
                twist.objective_conn = float(snapshot.objective_conn)
                twist.objective_axis = float(snapshot.objective_axis)
                twist.objective_pos = float(snapshot.objective_pos)
                twist.refinement_status = _STATUS_TO_ENUM.get(
                    snapshot.refinement_status, 0
                )
                twist.failure_reason = _FAILURE_TO_ENUM.get(
                    snapshot.failure_reason or "none", 12
                )
                twist.iterations = int(snapshot.iterations)
                twist.evaluations = int(snapshot.evaluations)
                twist.solve_duration_sec = float(snapshot.solve_duration_sec)
                writer.write(twist_topic, serialize_message(twist), stamp_ns)
        writer.close()

        output = root / "replay.json"
        assert replay.main(
            [str(bag), "--side", "left", "--params", str(params_path), "--output", str(output)]
        ) == 0
        summary = json.loads(output.read_text(encoding="utf-8"))
        assert summary["command"]["matched_frames"] > 0
        assert summary["command"]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)
        assert summary["twist"]["matched_frames"] > 0
        assert summary["twist"]["active_mismatches"] == 0
        assert summary["twist"]["status_mismatches"] == 0
        assert summary["twist"]["failure_mismatches"] == 0
        for name in (
            "theta_task", "theta_base", "theta_increment",
            "gate_aperture", "gate_extension", "objective_total",
        ):
            difference = summary["twist"][name]["max_abs_diff"]
            assert difference is None or difference <= 1e-9
