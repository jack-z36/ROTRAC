"""Offline twist-diagnosis analysis and MCAP reader tests."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import tempfile

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "analyze_twist_diagnosis.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "analyze_twist_diagnosis", _SCRIPT_PATH
)
analysis = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = analysis
_SPEC.loader.exec_module(analysis)


def _frame(stamp_ns, **overrides):
    values = {
        "stamp_ns": stamp_ns,
        "valid": True,
        "active": False,
        "gate_aperture": 0.3,
        "gate_extension": 1.0,
        "gate_on_count": 0,
        "gate_off_count": 0,
        "theta_task": 0.0,
        "theta_base": 0.0,
        "theta_increment": 0.0,
        "theta_robot_cmd": math.nan,
        "theta_robot_fb": math.nan,
        "theta_robot_fb_available": False,
        "axis_deviation_cmd_deg": math.nan,
        "axis_deviation_fb_deg": math.nan,
        "axis_deviation_fb_available": False,
        "objective_total": math.nan,
        "objective_rot": math.nan,
        "objective_conn": math.nan,
        "objective_axis": math.nan,
        "objective_pos": math.nan,
        "refinement_status": "not_active",
        "failure_reason": "none",
        "iterations": 0,
        "evaluations": 0,
        "solve_duration_sec": math.nan,
    }
    values.update(overrides)
    return values


def test_angle_metrics_use_feedback_minus_increment():
    frames = [
        _frame(
            0,
            active=True,
            theta_increment=0.1,
            theta_robot_fb=0.12,
            theta_robot_fb_available=True,
            theta_robot_cmd=0.11,
            axis_deviation_fb_deg=1.0,
            axis_deviation_fb_available=True,
            axis_deviation_cmd_deg=0.5,
            refinement_status="applied",
        ),
        _frame(
            1,
            active=True,
            theta_increment=0.2,
            theta_robot_fb=0.18,
            theta_robot_fb_available=True,
            theta_robot_cmd=0.23,
            axis_deviation_fb_deg=2.0,
            axis_deviation_fb_available=True,
            axis_deviation_cmd_deg=1.0,
            refinement_status="applied",
        ),
        _frame(
            2,
            active=True,
            theta_increment=0.3,
            theta_robot_fb=0.33,
            theta_robot_fb_available=True,
            theta_robot_cmd=0.25,
            axis_deviation_fb_deg=3.0,
            axis_deviation_fb_available=True,
            axis_deviation_cmd_deg=1.5,
            refinement_status="fallback_baseline",
            failure_reason="axis_deviation",
        ),
    ]
    summary = analysis.summarize(frames, "left")
    feedback = summary["angle_feedback"]
    assert feedback["sample_count"] == 3
    assert feedback["rmse_rad"] == pytest.approx(
        math.sqrt((0.02**2 + 0.02**2 + 0.03**2) / 3.0)
    )
    assert feedback["mae_rad"] == pytest.approx((0.02 + 0.02 + 0.03) / 3.0)
    assert feedback["pearson"] == pytest.approx(0.9707253433941511)
    command = summary["angle_command"]
    assert command["sample_count"] == 3
    assert command["rmse_rad"] == pytest.approx(
        math.sqrt((0.01**2 + 0.03**2 + 0.05**2) / 3.0)
    )
    assert summary["axis_deviation_feedback_deg"]["mean"] == pytest.approx(2.0)
    assert summary["axis_deviation_feedback_deg"]["max"] == pytest.approx(3.0)
    assert summary["refinement"]["applied_frames"] == 2
    assert summary["refinement"]["fallback_frames"] == 1
    assert summary["refinement"]["applied_ratio"] == pytest.approx(2.0 / 3.0)
    assert summary["refinement"]["failure_reason_counts"] == {
        "axis_deviation": 1
    }
    assert summary["object_rotation_measured"] is False
    assert "未测" in summary["object_rotation_note"]


def test_missing_feedback_no_active_interval_and_zero_variance_do_not_crash():
    frames = [
        _frame(0, valid=True, active=False),
        _frame(1, valid=False, active=False),
    ]
    summary = analysis.summarize(frames, "left")
    assert summary["active_frame_count"] == 0
    assert summary["active_frame_ratio"] == 0.0
    assert summary["angle_feedback"]["available"] is False
    assert summary["angle_feedback"]["rmse_rad"] is None
    assert summary["refinement"]["applied_ratio"] is None
    assert summary["feedback_available_ratio"] is None
    assert summary["negative_gate"]["available"] is False

    flat_active = [
        _frame(
            0,
            active=True,
            theta_increment=0.2,
            theta_robot_fb=0.2,
            theta_robot_fb_available=True,
        ),
        _frame(
            1,
            active=True,
            theta_increment=0.2,
            theta_robot_fb=0.2,
            theta_robot_fb_available=True,
        ),
    ]
    flat = analysis.summarize(flat_active, "left")
    assert flat["angle_feedback"]["rmse_rad"] == pytest.approx(0.0)
    assert flat["angle_feedback"]["pearson"] is None

    nan_feedback = [
        _frame(
            0,
            active=True,
            theta_increment=0.2,
            theta_robot_fb=math.nan,
            theta_robot_fb_available=True,
        )
    ]
    nan_summary = analysis.summarize(nan_feedback, "left")
    assert nan_summary["angle_feedback"]["available"] is False
    assert nan_summary["feedback_available_ratio"] == 0.0


def test_pearson_handles_degenerate_inputs():
    assert analysis.pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(
        1.0
    )
    assert analysis.pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(
        -1.0
    )
    assert analysis.pearson([1.0], [2.0]) is None
    assert analysis.pearson([1.0, 1.0], [1.0, 2.0]) is None


def test_negative_window_false_trigger_rate_and_episodes():
    frames = [
        _frame(0, active=False),
        _frame(1_000_000_000, active=True),
        _frame(2_000_000_000, active=True),
        _frame(3_000_000_000, active=False),
        _frame(4_000_000_000, active=True),
    ]
    summary = analysis.summarize(
        frames, "left", negative_windows=[(0.0, 3.0), (3.5, 5.0)]
    )
    gate = summary["negative_gate"]
    assert gate["available"] is True
    assert gate["valid_frames"] == 5
    assert gate["active_frames"] == 3
    assert gate["false_trigger_rate"] == pytest.approx(3.0 / 5.0)
    assert gate["activation_episodes"] == 2
    assert gate["windows"][0]["activation_episodes"] == 1


def test_write_frames_csv_contains_all_columns(tmp_path):
    frames = [_frame(0, active=True)]
    output = tmp_path / "frames.csv"
    analysis.write_frames_csv(frames, output)
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == list(analysis._FRAME_COLUMNS)
    assert len(lines) == 2


def test_mcap_round_trip_reads_twist_state():
    pytest.importorskip("rosbag2_py")
    from rclpy.serialization import serialize_message
    from rokoko_omnihand_msgs.msg import TwistState
    from rosbag2_py import (
        ConverterOptions,
        StorageOptions,
        SequentialWriter,
        TopicMetadata,
    )

    topic = "/hand_retargeting/left/twist_state"
    with tempfile.TemporaryDirectory() as directory:
        bag = Path(directory) / "bag"
        writer = SequentialWriter()
        writer.open(
            StorageOptions(uri=str(bag), storage_id="mcap"),
            ConverterOptions(
                input_serialization_format="cdr",
                output_serialization_format="cdr",
            ),
        )
        writer.create_topic(
            TopicMetadata(
                0,
                topic,
                "rokoko_omnihand_msgs/msg/TwistState",
                "cdr",
            )
        )
        for index in range(2):
            message = TwistState()
            message.header.stamp.sec = index
            message.header.stamp.nanosec = 0
            message.side = "left"
            message.valid = True
            message.active = index == 1
            message.theta_increment = 0.1 * index
            message.theta_robot_fb = 0.1 * index
            message.theta_robot_fb_available = True
            message.refinement_status = (
                TwistState.REFINEMENT_APPLIED
                if index == 1
                else TwistState.REFINEMENT_NOT_ACTIVE
            )
            writer.write(topic, serialize_message(message), index)
        writer.close()

        frames = analysis.read_frames(bag, "left")
        assert len(frames) == 2
        assert frames[0]["refinement_status"] == "not_active"
        assert frames[1]["refinement_status"] == "applied"
        summary = analysis.summarize(frames, "left")
        assert summary["active_frame_count"] == 1
        assert summary["angle_feedback"]["sample_count"] == 1
