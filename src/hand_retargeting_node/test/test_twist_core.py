"""Pure tests for the DexTwist tripod gate, intent and analytic refinement."""

import ast
import math
from pathlib import Path

from hand_retargeting.contracts import TwistConfig
from hand_retargeting.core.twist import (
    average_twist_angle,
    build_tripod_reference,
    evaluate_tripod_objective,
    gate_aperture,
    gate_extension,
    HumanTwistTracker,
    measure_tripod_state,
    refine_tripod,
    TripodProblem,
    TwistGate,
)
import numpy as np
from omnihand_o10_contracts import JOINT_LIMITS, Side
import pytest


def _config(**overrides):
    values = {
        "gate_aperture_on": 0.45,
        "gate_aperture_off": 0.70,
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
        "gradient_tolerance": 1e-3,
        "axis_epsilon": 1e-6,
        "projection_epsilon": 1e-4,
        "axis_deviation_limit_deg": 60.0,
    }
    values.update(overrides)
    return TwistConfig(**values)


class FakeCoupling:
    def evaluate(self, active):
        active = np.asarray(active, dtype=np.float64)
        full = np.zeros(16, dtype=np.float64)
        full[:10] = active
        return full

    def jacobian(self, active):
        result = np.zeros((16, 10), dtype=np.float64)
        result[:10, :10] = np.eye(10)
        return result


class FakeTripodKinematics:
    """Linear tip model: enough to check every analytic partial derivative."""

    def __init__(self):
        self.base = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=np.float64,
        )
        self.matrix = np.zeros((3, 3, 16), dtype=np.float64)
        self.matrix[0, 0, 0] = 1.0
        self.matrix[0, 1, 1] = 0.5
        self.matrix[0, 2, 2] = 0.5
        self.matrix[1, 0, 3] = 1.0
        self.matrix[1, 1, 4] = 0.5
        self.matrix[2, 0, 5] = 1.0
        self.matrix[2, 2, 5] = 0.5

    def tip_positions_and_jacobians(self, full_q, tip_frames):
        positions = self.base + self.matrix @ np.asarray(full_q, dtype=np.float64)
        return positions, self.matrix


def _problem(**overrides):
    config = overrides.pop("config", _config())
    kinematics = FakeTripodKinematics()
    baseline = np.zeros(10, dtype=np.float64)
    points = kinematics.tip_positions_and_jacobians(
        np.zeros(16), ("thumb_tip", "index_tip", "middle_tip")
    )[0]
    reference = build_tripod_reference(
        points, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    )
    values = {
        "active_indices": (0, 1, 2, 3, 4, 5),
        "tip_frames": ("thumb_tip", "index_tip", "middle_tip"),
        "baseline": baseline,
        "lower": np.full(6, -1.0),
        "upper": np.full(6, 1.0),
        "reference": reference,
        "target_increment": 0.3,
        "length_scale": 1.0,
        "config": config,
    }
    values.update(overrides)
    return TripodProblem(**values)


def _limits(side):
    limits = JOINT_LIMITS[side]
    indices = (0, 1, 2, 3, 4, 5)
    return (
        np.asarray([limits.lower[index] for index in indices], dtype=np.float64),
        np.asarray([limits.upper[index] for index in indices], dtype=np.float64),
    )


def _gradient_states(side):
    lower, upper = _limits(side)
    span = upper - lower
    if side is Side.LEFT:
        fractions = (0.35, 0.65, 0.05, 0.95)
    else:
        fractions = (0.70, 0.30, 0.95, 0.05)
    return [
        lower + fraction * span
        for fraction in fractions
    ]


@pytest.mark.parametrize("side", (Side.LEFT, Side.RIGHT))
def test_analytic_gradient_matches_central_difference_at_multiple_states(side):
    lower, upper = _limits(side)
    for q in _gradient_states(side):
        problem = _problem(lower=lower, upper=upper)
        coupling = FakeCoupling()
        kinematics = FakeTripodKinematics()
        evaluation = evaluate_tripod_objective(q, problem, coupling, kinematics)
        assert evaluation.valid
        numerical = np.zeros(6)
        step = 1e-6
        for index in range(6):
            plus = q.copy()
            minus = q.copy()
            plus[index] += step
            minus[index] -= step
            # Do not let a finite-difference probe cross a joint limit: the
            # production evaluator correctly rejects such a candidate, which
            # would turn the comparison into a NaN.
            if not (lower[index] <= minus[index] and plus[index] <= upper[index]):
                numerical[index] = evaluation.gradient[index]
                continue
            plus_eval = evaluate_tripod_objective(
                plus, problem, coupling, kinematics
            )
            minus_eval = evaluate_tripod_objective(
                minus, problem, coupling, kinematics
            )
            assert plus_eval.valid and minus_eval.valid
            numerical[index] = (plus_eval.loss - minus_eval.loss) / (2.0 * step)
        assert np.allclose(evaluation.gradient, numerical, rtol=1e-5, atol=1e-7)


def test_reference_latches_axis_closure_centroid_and_plane_units():
    config = _config()
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    reference = build_tripod_reference(
        points, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    )
    assert reference is not None
    assert np.allclose(reference.axis, (0.0, 0.0, 1.0))
    assert np.allclose(reference.closure, (1.0, 1.0, math.sqrt(2.0)))
    assert np.allclose(reference.centroid, points.mean(axis=0))
    for unit in reference.in_plane_units:
        assert abs(float(np.dot(unit, reference.axis))) < 1e-12
        assert np.linalg.norm(unit) == pytest.approx(1.0)


def test_reference_rejects_a_degenerate_tripod():
    config = _config()
    collinear = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    assert build_tripod_reference(
        collinear, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    ) is None

    folded = np.array(
        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    assert build_tripod_reference(
        folded, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    ) is None


def test_measure_state_is_sign_aligned_and_reports_axis_deviation():
    config = _config()
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    reference = build_tripod_reference(
        points, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    )
    # Mirroring index and middle flips the raw normal; measure_tripod_state
    # must align it back to the latched reference before reporting deviation.
    flipped = np.array(
        [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    state = measure_tripod_state(
        flipped, reference, config.axis_epsilon, config.projection_epsilon
    )
    assert state is not None
    assert np.allclose(state.axis, reference.axis)
    assert state.axis_deviation == pytest.approx(0.0, abs=1e-12)

    tilted = points.copy()
    tilted[2] = (0.0, 1.0, 0.5)
    tilted_reference = build_tripod_reference(
        points, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    )
    tilted_state = measure_tripod_state(
        tilted, tilted_reference, config.axis_epsilon,
        config.projection_epsilon,
    )
    assert tilted_state is not None
    assert tilted_state.axis_deviation > 0.0


def test_human_tracker_aligns_axis_to_palm_normal_and_preserves_theta_base():
    config = _config()
    tracker = HumanTwistTracker(config)
    # Clockwise node order gives a -Z raw normal; activation still latches +Z.
    clockwise = np.array(
        [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    assert tracker.activate(clockwise)
    assert np.allclose(tracker.axis, (0.0, 0.0, 1.0))
    assert tracker.theta_base == pytest.approx(0.0)

    angle = 0.25
    rotation = np.array(
        [
            [math.cos(angle), -math.sin(angle), 0.0],
            [math.sin(angle), math.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    delta = tracker.update(clockwise @ rotation.T)
    assert delta == pytest.approx(angle, abs=1e-12)
    first_theta = tracker.theta_task
    tracker.deactivate()
    assert tracker.activate(clockwise @ rotation.T)
    assert tracker.theta_base == pytest.approx(first_theta, abs=1e-12)
    assert tracker.target_increment == pytest.approx(0.0, abs=1e-12)


def test_objective_terms_are_independently_observable_and_dimensionless():
    base = _problem()
    kinematics = FakeTripodKinematics()
    q = np.array([0.02, -0.01, 0.02, 0.01, -0.01, 0.02])
    evaluation = evaluate_tripod_objective(q, base, FakeCoupling(), kinematics)
    assert evaluation.valid
    assert evaluation.terms.total == pytest.approx(
        evaluation.terms.rot
        + evaluation.terms.conn
        + evaluation.terms.axis
        + evaluation.terms.pos
    )
    for term in ("rot", "conn", "axis", "pos"):
        assert getattr(evaluation.terms, term) > 0.0

    weights = {
        "weight_rot": 0.0,
        "weight_conn": 0.0,
        "weight_axis": 0.0,
        "weight_pos": 0.0,
    }
    zeroed = _problem(config=_config(**weights))
    zero_eval = evaluate_tripod_objective(
        q, zeroed, FakeCoupling(), kinematics
    )
    assert zero_eval.terms.total == pytest.approx(0.0)
    for term in ("rot", "conn", "axis", "pos"):
        assert getattr(zero_eval.terms, term) == pytest.approx(0.0)

    scaled = _problem(length_scale=2.0)
    scaled_eval = evaluate_tripod_objective(
        q, scaled, FakeCoupling(), kinematics
    )
    assert scaled_eval.terms.rot == pytest.approx(evaluation.terms.rot)
    assert scaled_eval.terms.axis == pytest.approx(evaluation.terms.axis)
    assert scaled_eval.terms.conn == pytest.approx(
        evaluation.terms.conn / 4.0
    )
    assert scaled_eval.terms.pos == pytest.approx(evaluation.terms.pos / 4.0)


@pytest.mark.parametrize("iterations", (1, 3))
def test_refinement_respects_step_max_and_trust_region(iterations):
    step_problem = _problem(
        config=_config(iterations=iterations, step_max=0.001, trust_region=1.0)
    )
    step_refinement = refine_tripod(
        step_problem, FakeCoupling(), FakeTripodKinematics()
    )
    if step_refinement.candidate is not None:
        max_step = step_problem.config.step_max * iterations + 1e-12
        assert np.max(np.abs(step_refinement.candidate)) <= max_step

    trust_problem = _problem(
        config=_config(iterations=iterations, step_max=1.0, trust_region=0.0005)
    )
    trust_refinement = refine_tripod(
        trust_problem, FakeCoupling(), FakeTripodKinematics()
    )
    if trust_refinement.candidate is not None:
        assert np.max(np.abs(trust_refinement.candidate)) <= 0.0005 + 1e-12


def test_refinement_stops_early_when_the_gradient_is_small():
    problem = _problem(
        target_increment=0.0,
        config=_config(gradient_tolerance=1.0e9),
    )
    refinement = refine_tripod(problem, FakeCoupling(), FakeTripodKinematics())
    assert refinement.applied is True
    assert refinement.iterations == 1
    assert refinement.evaluations == 1


def test_objective_rejects_nonfinite_limits_and_degenerate_geometry():
    problem = _problem()
    coupling = FakeCoupling()
    kinematics = FakeTripodKinematics()
    assert evaluate_tripod_objective(
        np.array([math.nan, 0.0, 0.0, 0.0, 0.0, 0.0]),
        problem, coupling, kinematics,
    ).failure == "nonfinite"
    assert evaluate_tripod_objective(
        np.full(6, 10.0), problem, coupling, kinematics
    ).failure == "limits"

    class _DegenerateKinematics(FakeTripodKinematics):
        def tip_positions_and_jacobians(self, full_q, tip_frames):
            positions, jacobians = super().tip_positions_and_jacobians(
                full_q, tip_frames
            )
            positions[1] = positions[0]
            positions[2] = positions[0]
            return positions, jacobians

    degenerate = evaluate_tripod_objective(
        np.zeros(6), problem, coupling, _DegenerateKinematics()
    )
    assert degenerate.failure == "degenerate-tripod"


def test_core_twist_module_has_no_runtime_backend_imports():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "hand_retargeting"
        / "core"
        / "twist.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint({"rclpy", "pinocchio", "nlopt"})


def test_gate_uses_hysteresis_and_ignores_invalid_frames():
    config = _config()
    gate = TwistGate(config)
    for _ in range(2):
        gate.update(0.4, 0.8, True)
    assert gate.active is False
    gate.update(0.4, 0.8, True)
    assert gate.active is True
    assert gate.just_activated is True

    gate.update(None, None, False)
    assert gate.active is True

    for _ in range(2):
        gate.update(0.8, 0.8, True)
    assert gate.active is True
    gate.update(0.8, 0.8, True)
    assert gate.active is False
    assert gate.just_deactivated is True


def test_gate_aperture_is_normalized_by_the_frozen_scale():
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    assert gate_aperture(points, 1.0) == pytest.approx(math.sqrt(2.0))
    assert gate_aperture(points, 2.0) == pytest.approx(math.sqrt(2.0) / 2.0)
    with pytest.raises(ValueError):
        gate_aperture(points, 0.0)


def test_gate_extension_rejects_a_fist_like_pinch():
    config = _config()
    gate = TwistGate(config)
    for _ in range(5):
        gate.update(0.3, 0.2, True)
    assert gate.active is False


def test_human_tracker_accumulates_and_clips_across_regrasp():
    config = _config()
    tracker = HumanTwistTracker(config)
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    assert tracker.activate(points)
    angle = 0.2
    rotation = np.array(
        [
            [math.cos(angle), -math.sin(angle), 0.0],
            [math.sin(angle), math.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    delta = tracker.update(points @ rotation.T)
    assert delta == pytest.approx(angle, abs=1e-12)
    assert tracker.target_increment == pytest.approx(angle, abs=1e-12)
    tracker.deactivate()
    assert tracker.theta_task == pytest.approx(angle, abs=1e-12)
    assert tracker.activate(points @ rotation.T)
    assert tracker.target_increment == pytest.approx(0.0, abs=1e-12)
    clipped = tracker.update(points @ np.array(
        [
            [math.cos(1.5), -math.sin(1.5), 0.0],
            [math.sin(1.5), math.cos(1.5), 0.0],
            [0.0, 0.0, 1.0],
        ]
    ).T)
    assert clipped == pytest.approx(config.delta_theta_clip, abs=1e-12)


def test_average_twist_angle_is_zero_for_an_unaltered_tripod():
    axis = np.array([0.0, 0.0, 1.0])
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    assert average_twist_angle(points, points, axis, 1e-6) == pytest.approx(0.0)


def test_measure_tripod_state_reports_reference_identical_state_as_zero():
    config = _config()
    points = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    reference = build_tripod_reference(
        points, np.array([0.0, 0.0, 1.0]), config.axis_epsilon,
        config.projection_epsilon,
    )
    state = measure_tripod_state(
        points, reference, config.axis_epsilon, config.projection_epsilon
    )
    assert state.theta == pytest.approx(0.0)
    assert state.axis_deviation == pytest.approx(0.0)
    assert gate_aperture(points, 1.0) == pytest.approx(math.sqrt(2.0))
    assert gate_extension(points, 1.0) == pytest.approx(
        np.linalg.norm(points.mean(axis=0))
    )


def test_refinement_stays_inside_trust_region_and_improves_tracking():
    problem = _problem()
    refinement = refine_tripod(problem, FakeCoupling(), FakeTripodKinematics())
    assert refinement.applied is True
    assert refinement.candidate is not None
    assert np.max(np.abs(refinement.candidate)) <= problem.config.trust_region + 1e-9
    assert refinement.state is not None
    baseline = evaluate_tripod_objective(
        np.zeros(6), problem, FakeCoupling(), FakeTripodKinematics()
    )
    assert refinement.terms.total <= baseline.loss


def test_refinement_falls_back_when_axis_moves_too_far(monkeypatch):
    problem = _problem(config=_config(axis_deviation_limit_deg=1e-6))
    refinement = refine_tripod(problem, FakeCoupling(), FakeTripodKinematics())
    assert refinement.applied is False
    assert refinement.failure in ("axis-deviation", "trust-region", None)
