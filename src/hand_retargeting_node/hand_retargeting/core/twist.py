"""
Pure DexTwist tripod gate, intent tracking and residual refinement.

This module is deliberately independent of ROS, Pinocchio and NLopt. The
Application layer injects the O10 coupling and a small tripod-kinematics
Protocol, so the same math can be unit-tested without the numeric runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from ..contracts import TwistConfig

# The tripod is thumb-index-middle. Points are rows in that order.
TRIPOD_ACTIVE_INDICES = (0, 1, 2, 3, 4, 5)
TRIPOD_TIP_BASES = ("thumb_tip", "index_tip", "middle_tip")
PALM_NORMAL = np.array([0.0, 0.0, 1.0], dtype=np.float64)


def _as_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(points, dtype=np.float64)
    if array.shape != (3, 3) or not np.all(np.isfinite(array)):
        raise ValueError("tripod points must be a finite 3x3 array")
    return array


def _unit(vector: np.ndarray, epsilon: float) -> np.ndarray | None:
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= epsilon:
        return None
    return vector / norm


def _project_perp(vector: np.ndarray, axis: np.ndarray) -> np.ndarray:
    return vector - float(np.dot(vector, axis)) * axis


def _pairwise_distances(points: np.ndarray) -> np.ndarray:
    return np.array(
        [
            np.linalg.norm(points[1] - points[0]),
            np.linalg.norm(points[2] - points[0]),
            np.linalg.norm(points[2] - points[1]),
        ],
        dtype=np.float64,
    )


def _raw_normal(points: np.ndarray) -> np.ndarray:
    return np.cross(points[1] - points[0], points[2] - points[0])


def tripod_axis(
    points: Sequence[Sequence[float]],
    sign_hint: np.ndarray,
    epsilon: float,
) -> np.ndarray | None:
    """Return the tripod normal, sign-aligned to ``sign_hint``."""
    array = _as_points(points)
    raw = _raw_normal(array)
    axis = _unit(raw, epsilon)
    if axis is None:
        return None
    if float(np.dot(axis, sign_hint)) < 0.0:
        axis = -axis
    return axis


def _in_plane_units(
    points: np.ndarray,
    axis: np.ndarray,
    epsilon: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    vectors = []
    for index in (1, 2):
        projected = _project_perp(points[index] - points[0], axis)
        unit = _unit(projected, epsilon)
        if unit is None:
            return None
        vectors.append(unit)
    return vectors[0], vectors[1]


def _signed_angle(
    reference: np.ndarray,
    current: np.ndarray,
    axis: np.ndarray,
) -> float:
    return float(
        np.arctan2(
            float(np.dot(axis, np.cross(reference, current))),
            float(np.dot(reference, current)),
        )
    )


def _vector_angle(
    previous: np.ndarray,
    current: np.ndarray,
    axis: np.ndarray,
    epsilon: float,
) -> float | None:
    previous_unit = _unit(_project_perp(previous, axis), epsilon)
    current_unit = _unit(_project_perp(current, axis), epsilon)
    if previous_unit is None or current_unit is None:
        return None
    return _signed_angle(previous_unit, current_unit, axis)


def average_twist_angle(
    previous_points: Sequence[Sequence[float]],
    current_points: Sequence[Sequence[float]],
    axis: np.ndarray,
    epsilon: float,
) -> float | None:
    """Average the in-plane rotation of the index and middle tripod edges."""
    previous = _as_points(previous_points)
    current = _as_points(current_points)
    angles = []
    for index in (1, 2):
        angle = _vector_angle(
            previous[index] - previous[0],
            current[index] - current[0],
            axis,
            epsilon,
        )
        if angle is None:
            return None
        angles.append(angle)
    return 0.5 * (angles[0] + angles[1])


def gate_aperture(points: Sequence[Sequence[float]], scale: float) -> float:
    """Normalize the largest tripod edge by the frozen tripod length scale."""
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("tripod scale must be positive and finite")
    return float(np.max(_pairwise_distances(_as_points(points))) / scale)


def gate_extension(points: Sequence[Sequence[float]], scale: float) -> float:
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("tripod scale must be positive and finite")
    centroid = _as_points(points).mean(axis=0)
    return float(np.linalg.norm(centroid) / scale)


@dataclass(frozen=True)
class TripodReference:
    axis: np.ndarray
    closure: np.ndarray
    centroid: np.ndarray
    in_plane_units: tuple[np.ndarray, np.ndarray]


@dataclass(frozen=True)
class TripodState:
    axis: np.ndarray
    closure: np.ndarray
    centroid: np.ndarray
    theta: float
    axis_deviation: float


def build_tripod_reference(
    points: Sequence[Sequence[float]],
    sign_hint: np.ndarray,
    axis_epsilon: float,
    projection_epsilon: float,
) -> TripodReference | None:
    array = _as_points(points)
    axis = tripod_axis(array, sign_hint, axis_epsilon)
    if axis is None:
        return None
    units = _in_plane_units(array, axis, projection_epsilon)
    if units is None:
        return None
    return TripodReference(
        axis=axis,
        closure=_pairwise_distances(array),
        centroid=array.mean(axis=0),
        in_plane_units=units,
    )


def measure_tripod_state(
    points: Sequence[Sequence[float]],
    reference: TripodReference,
    axis_epsilon: float,
    projection_epsilon: float,
) -> TripodState | None:
    array = _as_points(points)
    raw = _raw_normal(array)
    axis = _unit(raw, axis_epsilon)
    if axis is None:
        return None
    if float(np.dot(axis, reference.axis)) < 0.0:
        axis = -axis
    units = _in_plane_units(array, reference.axis, projection_epsilon)
    if units is None:
        return None
    angles = [
        _signed_angle(reference.in_plane_units[index], units[index], reference.axis)
        for index in range(2)
    ]
    return TripodState(
        axis=axis,
        closure=_pairwise_distances(array),
        centroid=array.mean(axis=0),
        theta=0.5 * (angles[0] + angles[1]),
        axis_deviation=float(
            np.arccos(np.clip(float(np.dot(axis, reference.axis)), -1.0, 1.0))
        ),
    )


@dataclass
class TwistGate:
    """Hysteretic tripod activation over normalized aperture and extension."""

    config: TwistConfig
    active: bool = False
    on_count: int = 0
    off_count: int = 0
    just_activated: bool = False
    just_deactivated: bool = False

    def update(
        self,
        aperture: float | None,
        extension: float | None,
        valid: bool,
    ) -> None:
        self.just_activated = False
        self.just_deactivated = False
        if not valid or aperture is None or extension is None:
            return
        if self.active:
            if (
                aperture > self.config.gate_aperture_off
                or extension < self.config.gate_extension_min
            ):
                self.off_count += 1
                if self.off_count >= self.config.gate_off_frames:
                    self.active = False
                    self.on_count = 0
                    self.off_count = 0
                    self.just_deactivated = True
            else:
                self.off_count = 0
        else:
            if (
                aperture < self.config.gate_aperture_on
                and extension > self.config.gate_extension_min
            ):
                self.on_count += 1
                if self.on_count >= self.config.gate_on_frames:
                    self.active = True
                    self.on_count = 0
                    self.off_count = 0
                    self.just_activated = True
            else:
                self.on_count = 0


@dataclass
class HumanTwistTracker:
    """Accumulate the operator's twist intent across re-grasps."""

    config: TwistConfig
    theta_task: float = 0.0
    theta_base: float = 0.0
    active: bool = False
    axis: np.ndarray | None = None
    previous_points: np.ndarray | None = None
    last_delta: float = 0.0
    valid: bool = True

    @property
    def target_increment(self) -> float:
        return self.theta_task - self.theta_base

    def activate(self, points: Sequence[Sequence[float]]) -> bool:
        array = _as_points(points)
        axis = tripod_axis(array, PALM_NORMAL, self.config.axis_epsilon)
        if axis is None:
            return False
        if _in_plane_units(array, axis, self.config.projection_epsilon) is None:
            return False
        self.axis = axis
        self.previous_points = array.copy()
        self.active = True
        self.valid = True
        self.last_delta = 0.0
        self.theta_base = self.theta_task
        return True

    def update(self, points: Sequence[Sequence[float]]) -> float | None:
        if not self.active or self.axis is None or self.previous_points is None:
            return None
        array = _as_points(points)
        delta = average_twist_angle(
            self.previous_points, array, self.axis, self.config.projection_epsilon
        )
        if delta is None:
            self.valid = False
            return None
        delta = float(
            np.clip(delta, -self.config.delta_theta_clip, self.config.delta_theta_clip)
        )
        self.theta_task += delta
        self.last_delta = delta
        self.previous_points = array.copy()
        self.valid = True
        return delta

    def deactivate(self) -> None:
        self.active = False
        self.previous_points = None
        self.last_delta = 0.0


@dataclass(frozen=True)
class TwistObjectiveTerms:
    total: float
    rot: float
    conn: float
    axis: float
    pos: float


class TripodKinematics(Protocol):
    def tip_positions_and_jacobians(
        self, full_q: np.ndarray, tip_frames: Sequence[str]
    ) -> tuple[np.ndarray, np.ndarray]: ...


@dataclass(frozen=True)
class TripodProblem:
    active_indices: tuple[int, ...]
    tip_frames: tuple[str, str, str]
    baseline: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    reference: TripodReference
    target_increment: float
    length_scale: float
    config: TwistConfig

    def __post_init__(self) -> None:
        if len(self.active_indices) != 6:
            raise ValueError("tripod problem must optimize six active joints")
        if np.asarray(self.baseline).shape != (10,):
            raise ValueError("tripod baseline must be a 10-vector")
        if not np.isfinite(self.length_scale) or self.length_scale <= 0.0:
            raise ValueError("tripod length scale must be positive and finite")


@dataclass(frozen=True)
class TripodEvaluation:
    loss: float
    gradient: np.ndarray
    terms: TwistObjectiveTerms
    state: TripodState | None
    valid: bool
    failure: str | None = None


@dataclass(frozen=True)
class TwistRefinement:
    candidate: np.ndarray | None
    applied: bool
    failure: str | None
    terms: TwistObjectiveTerms
    state: TripodState | None
    iterations: int
    evaluations: int


def _failure_terms(failure: str, loss: float = float("nan")) -> TripodEvaluation:
    return TripodEvaluation(
        loss=loss,
        gradient=np.zeros(6, dtype=np.float64),
        terms=TwistObjectiveTerms(
            loss, float("nan"), float("nan"), float("nan"), float("nan")
        ),
        state=None,
        valid=False,
        failure=failure,
    )


def evaluate_tripod_objective(
    active: Sequence[float],
    problem: TripodProblem,
    coupling,
    kinematics: TripodKinematics,
) -> TripodEvaluation:
    config = problem.config
    q = np.asarray(active, dtype=np.float64)
    if q.shape != (6,) or not np.all(np.isfinite(q)):
        return _failure_terms("nonfinite")
    if np.any(q < problem.lower) or np.any(q > problem.upper):
        return _failure_terms("limits")

    full = np.asarray(problem.baseline, dtype=np.float64).copy()
    full[list(problem.active_indices)] = q
    full_state = coupling.evaluate(full)
    coupling_jacobian = coupling.jacobian(full)[:, list(problem.active_indices)]
    positions, jacobians = kinematics.tip_positions_and_jacobians(
        full_state, problem.tip_frames
    )
    positions = np.asarray(positions, dtype=np.float64)
    jacobians = np.asarray(jacobians, dtype=np.float64)
    if positions.shape != (3, 3) or jacobians.shape != (3, 3, 16):
        raise ValueError(
            "tripod kinematics must return 3x3 positions and 3x3x16 Jacobians"
        )
    if not np.all(np.isfinite(positions)) or not np.all(np.isfinite(jacobians)):
        return _failure_terms("nonfinite")

    jacobian = np.stack(
        [jacobians[index] @ coupling_jacobian for index in range(3)], axis=0
    )
    reference = problem.reference
    scale = problem.length_scale

    v0 = positions[1] - positions[0]
    v1 = positions[2] - positions[0]
    dv0 = jacobian[1] - jacobian[0]
    dv1 = jacobian[2] - jacobian[0]

    d01 = float(np.linalg.norm(v0))
    d02 = float(np.linalg.norm(v1))
    d12 = float(np.linalg.norm(v1 - v0))
    if min(d01, d02, d12) <= config.axis_epsilon:
        return _failure_terms("degenerate-tripod")
    closure = np.array([d01, d02, d12], dtype=np.float64)
    closure_jacobian = np.stack(
        [
            (v0 / d01) @ dv0,
            (v1 / d02) @ dv1,
            ((v1 - v0) / d12) @ (dv1 - dv0),
        ],
        axis=0,
    )
    conn = config.weight_conn * float(
        np.sum(((closure - reference.closure) / scale) ** 2)
    )
    gradient_conn = (
        2.0
        * config.weight_conn
        / (scale * scale)
        * (closure_jacobian.T @ (closure - reference.closure))
    )

    centroid = positions.mean(axis=0)
    centroid_jacobian = jacobian.mean(axis=0)
    centroid_error = centroid - reference.centroid
    pos = config.weight_pos * float(
        np.sum((centroid_error / scale) ** 2)
    )
    gradient_pos = (
        2.0
        * config.weight_pos
        / (scale * scale)
        * (centroid_jacobian.T @ centroid_error)
    )

    raw_normal = np.cross(v0, v1)
    normal_length = float(np.linalg.norm(raw_normal))
    if normal_length <= config.axis_epsilon:
        return _failure_terms("degenerate-tripod")
    normal = raw_normal / normal_length
    sign = 1.0 if float(np.dot(normal, reference.axis)) >= 0.0 else -1.0
    axis = sign * normal
    raw_normal_jacobian = (
        np.cross(dv0.T, v1).T + np.cross(v0, dv1.T).T
    )
    normal_jacobian = (
        (np.eye(3) - np.outer(normal, normal)) @ raw_normal_jacobian
    ) / normal_length
    axis_jacobian = sign * normal_jacobian
    axis_cosine = float(np.dot(axis, reference.axis))
    axis_term = config.weight_axis * (1.0 - axis_cosine * axis_cosine)
    gradient_axis = (
        -2.0
        * config.weight_axis
        * axis_cosine
        * (reference.axis @ axis_jacobian)
    )

    projection = np.eye(3) - np.outer(reference.axis, reference.axis)
    theta_sum = 0.0
    theta_jacobian = np.zeros(6, dtype=np.float64)
    for index, (raw_vector, raw_jacobian) in enumerate(
        ((v0, dv0), (v1, dv1))
    ):
        projected = projection @ raw_vector
        projected_norm = float(np.linalg.norm(projected))
        if projected_norm <= config.projection_epsilon:
            return _failure_terms("degenerate-tripod")
        current_unit = projected / projected_norm
        current_unit_jacobian = (
            (np.eye(3) - np.outer(current_unit, current_unit))
            @ projection
            @ raw_jacobian
        ) / projected_norm
        reference_unit = reference.in_plane_units[index]
        sine = float(
            np.dot(reference.axis, np.cross(reference_unit, current_unit))
        )
        cosine = float(np.dot(reference_unit, current_unit))
        theta_sum += float(np.arctan2(sine, cosine))
        dsine = np.cross(reference.axis, reference_unit) @ current_unit_jacobian
        dcosine = reference_unit @ current_unit_jacobian
        theta_jacobian += cosine * dsine - sine * dcosine
    theta = 0.5 * theta_sum
    theta_jacobian *= 0.5
    angle_error = theta - problem.target_increment
    rot = config.weight_rot * float(angle_error * angle_error)
    gradient_rot = (
        2.0 * config.weight_rot * angle_error * theta_jacobian
    )

    terms = TwistObjectiveTerms(
        total=rot + conn + axis_term + pos,
        rot=rot,
        conn=conn,
        axis=axis_term,
        pos=pos,
    )
    gradient = gradient_rot + gradient_conn + gradient_axis + gradient_pos
    if not np.all(np.isfinite(gradient)) or not np.isfinite(terms.total):
        return _failure_terms("nonfinite")
    state = TripodState(
        axis=axis,
        closure=closure,
        centroid=centroid,
        theta=theta,
        axis_deviation=float(np.arccos(np.clip(axis_cosine, -1.0, 1.0))),
    )
    return TripodEvaluation(
        loss=float(terms.total),
        gradient=gradient,
        terms=terms,
        state=state,
        valid=True,
    )


def refine_tripod(
    problem: TripodProblem,
    coupling,
    kinematics: TripodKinematics,
) -> TwistRefinement:
    config = problem.config
    baseline = np.asarray(
        problem.baseline[list(problem.active_indices)], dtype=np.float64
    )
    trust_lower = np.maximum(problem.lower, baseline - config.trust_region)
    trust_upper = np.minimum(problem.upper, baseline + config.trust_region)
    if np.any(trust_lower > trust_upper):
        return TwistRefinement(
            candidate=None,
            applied=False,
            failure="trust-region",
            terms=_failure_terms("trust-region").terms,
            state=None,
            iterations=0,
            evaluations=0,
        )

    q = baseline.copy()
    evaluation = evaluate_tripod_objective(q, problem, coupling, kinematics)
    evaluations = 1
    if not evaluation.valid:
        return TwistRefinement(
            candidate=None,
            applied=False,
            failure=evaluation.failure,
            terms=evaluation.terms,
            state=None,
            iterations=0,
            evaluations=evaluations,
        )

    iterations = 0
    for iteration in range(config.iterations):
        iterations = iteration + 1
        gradient_inf = float(np.max(np.abs(evaluation.gradient)))
        if gradient_inf <= config.gradient_tolerance:
            break
        direction = -evaluation.gradient / max(gradient_inf, 1e-12)
        step = config.step_max
        accepted = False
        for _ in range(3):
            candidate = q + step * direction
            candidate = np.clip(candidate, trust_lower, trust_upper)
            candidate_evaluation = evaluate_tripod_objective(
                candidate, problem, coupling, kinematics
            )
            evaluations += 1
            if (
                candidate_evaluation.valid
                and candidate_evaluation.loss < evaluation.loss
            ):
                q = candidate
                evaluation = candidate_evaluation
                accepted = True
                break
            step *= 0.5
        if not accepted:
            break

    if not evaluation.valid or evaluation.state is None:
        return TwistRefinement(
            candidate=None,
            applied=False,
            failure=evaluation.failure or "nonfinite",
            terms=evaluation.terms,
            state=None,
            iterations=iterations,
            evaluations=evaluations,
        )
    if np.any(q < problem.lower) or np.any(q > problem.upper):
        failure = "limits"
    elif np.max(np.abs(q - baseline)) > config.trust_region + 1e-9:
        failure = "trust-region"
    elif evaluation.state.axis_deviation > np.deg2rad(
        config.axis_deviation_limit_deg
    ):
        failure = "axis-deviation"
    else:
        failure = None
    return TwistRefinement(
        candidate=q.copy() if failure is None else None,
        applied=failure is None,
        failure=failure,
        terms=evaluation.terms,
        state=evaluation.state,
        iterations=iterations,
        evaluations=evaluations,
    )
