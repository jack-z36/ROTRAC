"""Offline replay comparison tests (no hardware, no ROS graph)."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "replay_twist_diagnosis.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "replay_twist_diagnosis", _SCRIPT_PATH
)
replay = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = replay
_SPEC.loader.exec_module(replay)


def _stamp(seconds, nanos=0):
    return SimpleNamespace(sec=seconds, nanosec=nanos)


def _joint_state(seconds, positions):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=_stamp(seconds)),
        position=list(positions),
    )


def _twist(seconds, **overrides):
    values = {
        "header": SimpleNamespace(stamp=_stamp(seconds)),
        "active": True,
        "theta_task": 0.2,
        "theta_base": 0.0,
        "theta_increment": 0.2,
        "gate_aperture": 0.3,
        "gate_extension": 1.0,
        "objective_total": 0.01,
        "refinement_status": 1,
        "failure_reason": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _snapshot(**overrides):
    values = {
        "active": True,
        "theta_task": 0.2,
        "theta_base": 0.0,
        "theta_increment": 0.2,
        "gate_aperture": 0.3,
        "gate_extension": 1.0,
        "objective_total": 0.01,
        "refinement_status": "applied",
        "failure_reason": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_command_comparison_aligns_by_stamp_and_reports_differences():
    replayed = [
        (100_000_000_000, (1.0, 2.0, 3.0), None),
        (200_000_000_000, (1.0, 2.0, 3.0), None),
    ]
    recorded = [
        _joint_state(100.0, (1.0, 2.1, 3.0)),
        _joint_state(200.0, (1.0, 2.0, 3.0)),
    ]
    result = replay._compare_commands(replayed, recorded)
    assert result["matched_frames"] == 2
    assert result["max_abs_diff"] == pytest.approx(0.1)
    assert result["mean_abs_diff"] == pytest.approx(0.1 / 6.0)


def test_twist_comparison_reports_enum_and_value_mismatches():
    decision = SimpleNamespace(twist=_snapshot())
    replayed = [(100, (0.0,) * 10, decision)]
    recorded = [_twist(100.0)]
    result = replay._compare_twist(replayed, recorded)
    assert result["matched_frames"] == 1
    assert result["active_mismatches"] == 0
    assert result["status_mismatches"] == 0
    assert result["failure_mismatches"] == 0
    assert result["theta_increment"]["max_abs_diff"] == pytest.approx(0.0)

    mismatched = _twist(
        100.0, active=False, refinement_status=2, failure_reason=10
    )
    result = replay._compare_twist(replayed, [mismatched])
    assert result["active_mismatches"] == 1
    assert result["status_mismatches"] == 1
    assert result["failure_mismatches"] == 1


def test_max_abs_ignores_nan_and_handles_empty_input():
    assert replay._max_abs([1.0, -2.0, math.nan]) == pytest.approx(2.0)
    assert replay._max_abs([math.nan]) is None
    assert replay._mean_abs([]) is None


def test_config_from_params_reconstructs_twist_configuration():
    params = {
        "palm_y_epsilon": 1e-6,
        "palm_x_epsilon": 1e-6,
        "finger_length_epsilon": 1e-6,
        "length_window_size": 3,
        "stable_window_count": 2,
        "length_nmad_thresholds": [0.01] * 5,
        "frozen_length_relative_thresholds": [0.1] * 5,
        "ik_residual_thresholds": [0.05] * 5,
        "ik_max_evaluations": 100,
        "ik_max_time_sec": 0.02,
        "smooth_time_constants": [0.1] * 10,
        "stale_timeout_sec": 0.5,
        "recovery_min_valid_frames": 3,
        "recovery_min_duration_sec": 0.1,
        "thumb_roll_sensitivity": 1.0,
        "twist_gate_aperture_on": 0.45,
        "twist_gate_aperture_off": 0.70,
        "twist_gate_extension_min": 0.50,
        "twist_gate_on_frames": 3,
        "twist_gate_off_frames": 3,
        "twist_weight_rot": 1.0,
        "twist_weight_conn": 1.0,
        "twist_weight_axis": 0.5,
        "twist_weight_pos": 0.5,
        "twist_iterations": 5,
        "twist_step_max": 0.02,
        "twist_trust_region": 0.10,
        "twist_delta_theta_clip": 0.52,
        "twist_gradient_tolerance": 1e-3,
        "twist_axis_epsilon": 1e-6,
        "twist_projection_epsilon": 1e-4,
        "twist_axis_deviation_limit_deg": 60.0,
    }
    config = replay._config_from_params(params)
    assert config.twist is not None
    assert config.twist.gate_aperture_on == pytest.approx(0.45)
    assert config.twist.axis_deviation_limit_deg == pytest.approx(60.0)
    assert config.recovery_confirmation_timeout_sec == pytest.approx(0.5)
    assert config.thumb_abad_sensitivity == pytest.approx(1.0)
