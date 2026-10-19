"""Session-level tests for the DexTwist integration."""

import math

from hand_retargeting.application.session import RetargetingSession
from hand_retargeting.contracts import (
    RawHandFrameValue,
    RetargetingConfig,
    TwistConfig,
)
from hand_retargeting.core.normalization import (
    build_palm_frame,
    RobotHandGeometry,
)
import numpy as np
from omnihand_o10_contracts import Side
import pytest


NODE_NAMES = (
    "Hand",
    "ThumbProximal", "ThumbMedial", "ThumbDistal", "ThumbTip",
    "IndexProximal", "IndexMedial", "IndexDistal", "IndexTip",
    "MiddleProximal", "MiddleMedial", "MiddleDistal", "MiddleTip",
    "RingProximal", "RingMedial", "RingDistal", "RingTip",
    "LittleProximal", "LittleMedial", "LittleDistal", "LittleTip",
)
ROOTS = (0.8, 0.6, 0.2, -0.2, -0.6)


class FakeCoupling:
    def evaluate(self, active):
        values = np.asarray(active, dtype=np.float64)
        full = np.zeros(16, dtype=np.float64)
        full[:10] = values
        return full

    def jacobian(self, active):
        result = np.zeros((16, 10), dtype=np.float64)
        result[:10, :10] = np.eye(10)
        return result


class FakeTripodKinematics:
    def __init__(self):
        self.frames = ("thumb_tip", "index_tip", "middle_tip", "ring_tip", "pinky_tip")
        self.base = np.array(
            [
                [0.8, 1.0, 0.0],
                [0.6, 1.0, 0.0],
                [0.2, 1.0, 0.1],
                [-0.2, 1.0, 0.0],
                [-0.6, 1.0, 0.0],
            ],
            dtype=np.float64,
        )
        self.matrix = np.zeros((5, 3, 16), dtype=np.float64)
        for index in range(5):
            self.matrix[index, 0, min(index * 2, 9)] = 0.01
            self.matrix[index, 1, min(index * 2 + 1, 9)] = 0.01

    def _index(self, tip_frame):
        return self.frames.index(tip_frame.split("_", 1)[1])

    def tip_position_and_jacobian(self, full_q, tip_frame):
        index = self._index(tip_frame)
        tip = self.base[index] + self.matrix[index] @ np.asarray(full_q, dtype=np.float64)
        return tip, self.matrix[index]

    def tip_positions_and_jacobians(self, full_q, tip_frames):
        positions = []
        jacobians = []
        for frame in tip_frames:
            position, jacobian = self.tip_position_and_jacobian(full_q, frame)
            positions.append(position)
            jacobians.append(jacobian)
        return np.stack(positions), np.stack(jacobians)


class FakeOptimizer:
    def solve(self, problem, initial):
        class Result:
            pass

        result = Result()
        # A fixed zero baseline keeps the fake robot tripod's normal (+Y)
        # aligned with the mapped human tripod normal, so these tests exercise
        # the twist layer rather than the axis-mismatch fail-closed path.
        result.candidate = np.zeros(len(problem.active_indices), dtype=np.float64)
        result.solver_usable = True
        result.result_code = 0
        result.evaluations = 1
        return result


class RecordingOptimizer(FakeOptimizer):
    """Capture the warm start supplied to each finger solve."""

    def __init__(self):
        self.initials = []

    def solve(self, problem, initial):
        self.initials.append(np.asarray(initial, dtype=np.float64).copy())
        return super().solve(problem, initial)


def _twist_config(**overrides):
    values = {
        "gate_aperture_on": 0.65,
        "gate_aperture_off": 0.85,
        "gate_extension_min": 0.50,
        "gate_on_frames": 3,
        "gate_off_frames": 3,
        "weight_rot": 1.0,
        "weight_conn": 1.0,
        "weight_axis": 0.5,
        "weight_pos": 0.5,
        "iterations": 5,
        "step_max": 0.02,
        "trust_region": 0.10,
        "delta_theta_clip": 0.52,
        # The fake tripod kinematics has a deliberately weak angular gradient;
        # use a tighter test tolerance so refinement actually iterates. The
        # production value (1e-3) is covered by the pure-core early-stop test.
        "gradient_tolerance": 1e-6,
        "axis_epsilon": 1e-6,
        "projection_epsilon": 1e-4,
        "axis_deviation_limit_deg": 60.0,
    }
    values.update(overrides)
    return TwistConfig(**values)


def _config(
    twist,
    frozen_length_thresholds=(0.10,) * 5,
    smooth_time_constants=(0.1,) * 10,
    thumb_roll_sensitivity=1.0,
    thumb_abad_sensitivity=1.0,
    thumb_roll_fixed_value=None,
    thumb_abad_fixed_value=None,
):
    return RetargetingConfig(
        palm_y_epsilon=1e-6,
        palm_x_epsilon=1e-6,
        finger_length_epsilon=1e-6,
        length_window_size=3,
        stable_window_count=2,
        length_nmad_thresholds=(0.01,) * 5,
        frozen_length_relative_thresholds=frozen_length_thresholds,
        ik_residual_thresholds=(10.0,) * 5,
        ik_max_evaluations=10,
        ik_max_time_sec=0.01,
        smooth_time_constants=smooth_time_constants,
        stale_timeout_sec=0.5,
        recovery_min_valid_frames=3,
        recovery_min_duration_sec=0.1,
        recovery_confirmation_timeout_sec=0.5,
        thumb_roll_sensitivity=thumb_roll_sensitivity,
        twist=twist,
        thumb_abad_sensitivity=thumb_abad_sensitivity,
        thumb_roll_fixed_value=thumb_roll_fixed_value,
        thumb_abad_fixed_value=thumb_abad_fixed_value,
    )


def _geometry():
    return RobotHandGeometry(
        tuple((float(index), 0.0, 0.0) for index in range(5)),
        (3.0,) * 5,
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    )


def _base_positions():
    positions = [(0.0, 0.0, 0.0)]
    for root in ROOTS:
        positions.extend(
            [(root, 1.0, 0.0), (root, 1.4, 0.0), (root, 1.8, 0.0), (root, 2.2, 0.0)]
        )
    # A real tripod needs a non-collinear thumb tip.
    positions[4] = (0.4, 2.0, 0.2)
    return positions


def _frame(stamp, positions, side=Side.LEFT):
    return RawHandFrameValue(
        tuple(side.value + suffix for suffix in NODE_NAMES),
        tuple(positions),
        stamp,
    )


def _rotate_tripod(positions, config, angle):
    palm = build_palm_frame(tuple(positions), Side.LEFT, config)
    tip_indices = (4, 8, 12)
    palm_points = np.array([palm.from_world(positions[index]) for index in tip_indices])
    axis = np.cross(palm_points[1] - palm_points[0], palm_points[2] - palm_points[0])
    axis /= np.linalg.norm(axis)
    centroid = palm_points.mean(axis=0)
    skew = np.array(
        [[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]]
    )
    rotation = (
        np.eye(3)
        + math.sin(angle) * skew
        + (1.0 - math.cos(angle)) * (skew @ skew)
    )
    rotated = (rotation @ (palm_points - centroid).T).T + centroid
    result = list(positions)
    for index, point in zip(tip_indices, rotated):
        relative = point - palm.origin
        result[index] = tuple(
            palm.origin
            + relative[0] * np.asarray(palm.axes[0])
            + relative[1] * np.asarray(palm.axes[1])
            + relative[2] * np.asarray(palm.axes[2])
        )
    return result


def _session(
    twist,
    frozen_length_thresholds=(0.10,) * 5,
    geometry=None,
    side=Side.LEFT,
    optimizer=None,
    **config_overrides,
):
    return RetargetingSession(
        side,
        _config(
            twist,
            frozen_length_thresholds,
            **config_overrides,
        ),
        geometry if geometry is not None else _geometry(),
        coupling=FakeCoupling(),
        kinematics=FakeTripodKinematics(),
        optimizer=optimizer if optimizer is not None else FakeOptimizer(),
    )


def test_session_activates_twist_and_tracks_a_human_rotation():
    config = _config(_twist_config())
    session = _session(config.twist)
    positions = _base_positions()
    decision = None
    for index in range(6):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "applied"
    assert decision.twist.objective_total == pytest.approx(0.0, abs=1e-12)

    rotated = _rotate_tripod(positions, config, 0.2)
    decision = session.process(_frame(6 * 100_000_000, rotated))
    assert decision.twist.theta_increment == pytest.approx(0.2, abs=1e-12)
    assert decision.twist.theta_robot_cmd != 0.0
    assert decision.twist.refinement_status in ("applied", "fallback-baseline")

    session.update_feedback(decision.command_positions or (0.0,) * 10)
    decision = session.process(_frame(7 * 100_000_000, rotated))
    assert decision.twist.theta_robot_fb_available is True
    assert math.isfinite(decision.twist.theta_robot_fb)


def test_twist_exits_after_open_fingers_and_returns_to_baseline():
    session = _session(_twist_config(), frozen_length_thresholds=(10.0,) * 5)
    positions = _base_positions()
    for index in range(6):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist.active is True
    opened = list(positions)
    opened[4] = (-2.0, 1.0, 0.0)
    opened[8] = (2.0, 1.0, 0.0)
    opened[12] = (0.0, 3.0, 0.0)
    for index in range(6, 10):
        decision = session.process(_frame(index * 100_000_000, opened))
    assert decision.twist.active is False
    assert decision.twist.refinement_status == "not-active"


def test_axis_mismatch_falls_back_to_baseline():
    class _OrthogonalMappingGeometry:
        def __init__(self):
            base = _geometry()
            self.finger_roots = base.finger_roots
            self.finger_chain_lengths = base.finger_chain_lengths
            self.direction_mapping = base.direction_mapping

        def map_vector(self, vector):
            return (0.0, 0.0, 0.0)

    session = _session(_twist_config(), geometry=_OrthogonalMappingGeometry())
    positions = _base_positions()
    decision = None
    for index in range(6):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.refinement_status == "fallback-baseline"
    assert decision.twist.failure_reason == "axis-mismatch"


def test_feedback_never_changes_the_control_command():
    twist = _twist_config()
    with_feedback = _session(twist)
    without_feedback = _session(twist)
    positions = _base_positions()
    for index in range(10):
        stamp = index * 100_000_000
        frame = _frame(stamp, positions)
        decision_with = with_feedback.process(frame)
        decision_without = without_feedback.process(frame)
        assert decision_with.command_positions == decision_without.command_positions
        if decision_with.command_positions is not None:
            with_feedback.update_feedback(decision_with.command_positions, stamp)


def test_stale_resets_the_twist_episode_but_keeps_accumulated_theta():
    session = _session(_twist_config())
    positions = _base_positions()
    for index in range(6):
        session.process(_frame(index * 100_000_000, positions))
    rotated = _rotate_tripod(positions, _config(_twist_config()), 0.2)
    decision = session.process(_frame(6 * 100_000_000, rotated))
    theta = decision.twist.theta_task
    assert decision.twist.active is True

    stale = session.mark_stale()
    assert stale.twist.active is False
    assert stale.twist.valid is False
    assert stale.twist.theta_task == pytest.approx(theta)

    # Recovery needs a fresh, contiguous valid window before the gate can be
    # satisfied again; the accumulated human angle is never reset.
    for index in range(7, 13):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.theta_task == pytest.approx(theta)


def test_human_axis_opposite_to_the_robot_reference_fails_closed():
    class _ReversingGeometry:
        def __init__(self):
            base = _geometry()
            self.finger_roots = base.finger_roots
            self.finger_chain_lengths = base.finger_chain_lengths
            self.direction_mapping = (
                (1.0, 0.0, 0.0),
                (0.0, -1.0, 0.0),
                (0.0, 0.0, -1.0),
            )

        def map_vector(self, vector):
            return (vector[0], -vector[1], -vector[2])

    session = _session(_twist_config(), geometry=_ReversingGeometry())
    positions = _base_positions()
    decision = None
    for index in range(7):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "fallback-baseline"
    assert decision.twist.failure_reason == "axis-mismatch"
    assert decision.command_published is True
    assert math.isnan(decision.twist.theta_robot_cmd)


def test_thumb_fixed_values_are_skipped_during_twist_and_restored_after_exit():
    fixed_roll = -0.5
    fixed_abad = 0.8
    session = _session(
        _twist_config(),
        frozen_length_thresholds=(10.0,) * 5,
        smooth_time_constants=(0.005,) * 10,
        thumb_roll_fixed_value=fixed_roll,
        thumb_abad_fixed_value=fixed_abad,
    )
    positions = _base_positions()
    decision = None
    for index in range(7):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "applied"
    assert decision.command_positions is not None
    assert abs(decision.command_positions[0] - fixed_roll) > 1e-6
    assert abs(decision.command_positions[1] - fixed_abad) > 1e-6

    opened = list(positions)
    opened[4] = (-2.0, 1.0, 0.0)
    opened[8] = (2.0, 1.0, 0.0)
    opened[12] = (0.0, 3.0, 0.0)
    for index in range(7, 12):
        decision = session.process(_frame(index * 100_000_000, opened))
    assert decision.twist.active is False
    assert decision.command_positions is not None
    assert decision.command_positions[0] == pytest.approx(fixed_roll, abs=1e-6)
    assert decision.command_positions[1] == pytest.approx(fixed_abad, abs=1e-6)


def test_twist_refinement_leaves_ring_and_pinky_at_baseline():
    twisted = _session(_twist_config())
    baseline = _session(None)
    positions = _base_positions()
    for index in range(8):
        frame = _frame(index * 100_000_000, positions)
        twist_decision = twisted.process(frame)
        baseline_decision = baseline.process(frame)
        if twist_decision.command_positions is None:
            continue
        assert baseline_decision.command_positions is not None
        assert twist_decision.command_positions[6:] == pytest.approx(
            baseline_decision.command_positions[6:], abs=1e-12
        )


def test_refinement_does_not_advance_the_baseline_warm_start():
    optimizer = RecordingOptimizer()
    session = _session(_twist_config(), optimizer=optimizer)
    positions = _base_positions()
    decisions = [
        session.process(_frame(index * 100_000_000, positions))
        for index in range(9)
    ]
    assert decisions[6].twist.active is True
    assert decisions[6].twist.refinement_status == "applied"
    # Five solves per frame; the initial for every finger on frame 8 must be
    # the baseline candidate from frame 7, never the refined tripod command.
    previous = optimizer.initials[20:25]
    current = optimizer.initials[25:30]
    assert len(previous) == len(current) == 5
    for before, after in zip(previous, current):
        assert before == pytest.approx(after, abs=1e-12)


def test_baseline_incomplete_falls_back_without_publishing():
    class _RingFailingOptimizer(FakeOptimizer):
        def solve(self, problem, initial):
            result = super().solve(problem, initial)
            if problem.tip_frame.endswith("ring_tip"):
                result.solver_usable = False
            return result

    session = _session(_twist_config(), optimizer=_RingFailingOptimizer())
    positions = _base_positions()
    decisions = [
        session.process(_frame(index * 100_000_000, positions))
        for index in range(7)
    ]
    decision = decisions[-1]
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "fallback-baseline"
    assert decision.twist.failure_reason == "baseline-incomplete"
    assert decision.command_published is False


def test_left_and_right_twist_state_is_isolated():
    left = _session(_twist_config(), side=Side.LEFT)
    right = _session(_twist_config(), side=Side.RIGHT)
    positions = _base_positions()
    for index in range(7):
        left_decision = left.process(
            _frame(index * 100_000_000, positions, side=Side.LEFT)
        )
    assert left_decision.twist.active is True
    right_decision = right.process(
        _frame(700_000_000, positions, side=Side.RIGHT)
    )
    assert right_decision.twist is not None
    assert right_decision.twist.active is False
    assert right_decision.twist.theta_task == pytest.approx(0.0)


def test_backend_unavailable_is_reported_as_a_fallback():
    config = _config(_twist_config())
    session = RetargetingSession(Side.LEFT, config, _geometry())
    positions = _base_positions()
    decision = None
    for index in range(7):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "fallback-baseline"
    assert decision.twist.failure_reason == "backend-unavailable"
    assert decision.command_published is False


def test_solver_exception_falls_back_to_baseline(monkeypatch):
    import hand_retargeting.application.session as session_module

    def explode(*_args, **_kwargs):
        raise RuntimeError("numeric solver exploded")

    monkeypatch.setattr(session_module, "refine_tripod", explode)
    session = _session(_twist_config())
    positions = _base_positions()
    decision = None
    for index in range(7):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.active is True
    assert decision.twist.refinement_status == "fallback-baseline"
    assert decision.twist.failure_reason == "solver-error"
    assert decision.command_published is True


def test_twist_exit_converges_to_the_baseline_command():
    twisted = _session(
        _twist_config(), smooth_time_constants=(0.005,) * 10
    )
    baseline = _session(None, smooth_time_constants=(0.005,) * 10)
    positions = _base_positions()
    for index in range(6):
        frame = _frame(index * 100_000_000, positions)
        twisted.process(frame)
        baseline.process(frame)
    opened = list(positions)
    opened[4] = (-2.0, 1.0, 0.0)
    opened[8] = (2.0, 1.0, 0.0)
    opened[12] = (0.0, 3.0, 0.0)
    for index in range(6, 11):
        frame = _frame(index * 100_000_000, opened)
        twist_decision = twisted.process(frame)
        baseline_decision = baseline.process(frame)
        if twist_decision.twist.active:
            continue
        assert twist_decision.command_positions == pytest.approx(
            baseline_decision.command_positions, abs=1e-9
        )


def test_feedback_missing_is_nan_and_feedback_only_updates_diagnostics():
    session = _session(_twist_config())
    positions = _base_positions()
    decision = None
    for index in range(7):
        decision = session.process(_frame(index * 100_000_000, positions))
    assert decision.twist is not None
    assert decision.twist.theta_robot_fb_available is False
    assert math.isnan(decision.twist.theta_robot_fb)
    assert decision.twist.axis_deviation_fb_available is False
    assert math.isnan(decision.twist.axis_deviation_fb_deg)

    command = decision.command_positions
    assert command is not None
    session.update_feedback(command)
    decision = session.process(_frame(700_000_000, positions))
    assert decision.twist.theta_robot_fb_available is True
    assert math.isfinite(decision.twist.theta_robot_fb)
    assert decision.twist.axis_deviation_fb_available is True
    assert decision.command_positions == pytest.approx(command, abs=1e-12)
