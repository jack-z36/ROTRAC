"""Per-side T05 retargeting aggregate."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import time

import numpy as np
from omnihand_o10_contracts import Side
from omnihand_o10_contracts.joints import JOINT_LIMITS
from omnihand_o10_model.contract import tip_link

from ..contracts import (
    RawHandFrameValue,
    RetargetingConfig,
    RetargetingDecision,
    TwistSnapshot,
)
from ..core.anatomical_correction import correct_anatomical_human_vector
from ..core.coupling import CouplingModel
from ..core.ik import CandidateEvidence, FingerProblem, validate_candidate
from ..core.normalization import (
    build_palm_frame,
    finger_chain_length,
    finger_positions_in_palm,
    InvalidPalmFrame,
    normalized_mad,
    RobotHandGeometry,
    validate_frame,
)
from ..core.projection import build_projection_witness
from ..core.smoothing import LowPassFilter
from ..core.twist import (
    build_tripod_reference,
    gate_aperture,
    gate_extension,
    HumanTwistTracker,
    measure_tripod_state,
    PALM_NORMAL,
    refine_tripod,
    TRIPOD_ACTIVE_INDICES,
    TRIPOD_TIP_BASES,
    TripodProblem,
    TwistGate,
)


FINGER_ACTIVE_INDICES = ((0, 1, 2), (3, 4), (5,), (6, 7), (8, 9))
FINGER_TIP_BASES = ("thumb_tip", "index_tip", "middle_tip", "ring_tip", "pinky_tip")


class FingerOptimizerPort:
    """Small testable boundary implemented by the NLopt adapter."""

    def solve(
        self, problem: FingerProblem, initial: np.ndarray
    ):  # pragma: no cover - protocol seam
        raise NotImplementedError


@dataclass
class _LengthEstimator:
    window_size: int
    stable_window_count: int
    dispersion_threshold: float
    samples: deque[float] = field(init=False)
    consecutive_stable: int = 0
    frozen_length: float | None = None

    def __post_init__(self) -> None:
        self.samples = deque(maxlen=self.window_size)

    def observe(self, value: float) -> None:
        if self.frozen_length is not None:
            return
        self.samples.append(value)
        if len(self.samples) < self.window_size:
            return
        center, dispersion = normalized_mad(tuple(self.samples))
        if dispersion <= self.dispersion_threshold:
            self.consecutive_stable += 1
            if self.consecutive_stable >= self.stable_window_count:
                self.frozen_length = center
        else:
            self.consecutive_stable = 0


class RetargetingSession:
    """Own all mutable T05 history for one logical hand side."""

    def __init__(
        self,
        side: Side | str,
        config: RetargetingConfig,
        robot_geometry: RobotHandGeometry,
        *,
        coupling: CouplingModel | None = None,
        kinematics=None,
        optimizer: FingerOptimizerPort | None = None,
        clock=time.perf_counter,
    ) -> None:
        self.side = Side.from_value(side)
        self.config = config
        self.robot_geometry = robot_geometry
        self.coupling = coupling
        self.kinematics = kinematics
        self.optimizer = optimizer
        self._clock = clock
        self._last_valid = [None] * 5
        self._has_valid = [False] * 5
        self._filter = LowPassFilter(config.smooth_time_constants)
        self._stale = False
        self._recovery_frames = 0
        self._recovery_attempt_start_ns = None
        self._valid_streak_start_ns = None
        self._recovery_candidates = None
        self._last_input_at_ns: int | None = None
        self._twist_gate = TwistGate(config.twist) if config.twist is not None else None
        self._twist_tracker = (
            HumanTwistTracker(config.twist) if config.twist is not None else None
        )
        self._twist_tip_frames = tuple(
            tip_link(self.side.value, base) for base in TRIPOD_TIP_BASES
        )
        self._twist_reference = None
        self._twist_reference_pending = False
        self._twist_reference_failure = None
        self._last_aperture = math.nan
        self._last_extension = math.nan
        self._feedback_positions = None
        self._feedback_theta = math.nan
        self._feedback_axis_deviation = math.nan
        self._feedback_available = False
        self._estimators = tuple(
            _LengthEstimator(
                config.length_window_size,
                config.stable_window_count,
                config.length_nmad_thresholds[index],
            )
            for index in range(5)
        )

    def process(self, frame: RawHandFrameValue) -> RetargetingDecision:
        validate_frame(frame, self.side)
        self._last_input_at_ns = frame.received_at_ns
        try:
            palm = build_palm_frame(frame.positions, self.side, self.config)
        except InvalidPalmFrame:
            return self._decision(
                frame.received_at_ns,
                side_valid=False,
                current_lengths=None,
                twist_snapshot=self._twist_snapshot(
                    status="not-active", valid=False
                ),
            )

        finger_points = finger_positions_in_palm(frame, palm)
        current_lengths = tuple(
            finger_chain_length(points, self.config.finger_length_epsilon)
            for points in finger_points
        )
        for estimator, current_length in zip(self._estimators, current_lengths):
            if current_length is not None:
                estimator.observe(current_length)

        all_frozen = all(estimator.frozen_length is not None for estimator in self._estimators)
        targets = None
        if all_frozen:
            target_values = []
            for index, (points, current_length, estimator) in enumerate(
                zip(finger_points, current_lengths, self._estimators)
            ):
                frozen = estimator.frozen_length
                assert frozen is not None
                valid = current_length is not None and (
                    abs(current_length - frozen) / frozen
                    <= self.config.frozen_length_relative_thresholds[index]
                )
                if not valid:
                    target_values.append(None)
                    continue
                human_vector = tuple(
                    (points[3][axis] - points[0][axis]) / frozen for axis in range(3)
                )
                human_vector = correct_anatomical_human_vector(
                    self.side, index, human_vector
                )
                mapped = self.robot_geometry.map_vector(human_vector)
                root = self.robot_geometry.finger_roots[index]
                robot_length = self.robot_geometry.finger_chain_lengths[index]
                target_values.append(tuple(
                    root[axis] + robot_length * mapped[axis] for axis in range(3)
                ))
            targets = tuple(target_values)

        self._update_twist_state(finger_points, current_lengths, targets)

        if self.optimizer is None or self.coupling is None or self.kinematics is None:
            backend_unavailable = (
                self._twist_gate is not None and self._twist_gate.active
            )
            return self._decision(
                frame.received_at_ns, side_valid=True, current_lengths=current_lengths,
                targets=targets,
                twist_snapshot=self._twist_snapshot(
                    status="fallback-baseline" if backend_unavailable else "not-active",
                    failure="backend-unavailable" if backend_unavailable else None,
                ),
            )
        if self._stale:
            return self._process_recovery(
                frame, current_lengths, targets, side_valid=True
            )
        return self._solve_and_publish(
            frame.received_at_ns, current_lengths, targets, side_valid=True
        )

    def mark_stale(self) -> RetargetingDecision:
        """Freeze output and time history until a caller supplies recovery frames."""
        self._stale = True
        self._recovery_frames = 0
        self._recovery_attempt_start_ns = None
        self._valid_streak_start_ns = None
        self._recovery_candidates = None
        self._reset_twist_episode()
        return self._decision(
            self._filter.last_stamp_ns or 0,
            side_valid=False,
            current_lengths=None,
            targets=None,
            stale=True,
            twist_snapshot=self._twist_snapshot(status="not-active", valid=False),
        )

    def check_stale(self, now_ns: int) -> RetargetingDecision | None:
        """Enter stale after the configured receive-time silence interval."""
        if self._stale or self._last_input_at_ns is None:
            return None
        if now_ns - self._last_input_at_ns > self.config.stale_timeout_sec * 1e9:
            return self.mark_stale()
        return None

    def update_feedback(self, positions, received_at_ns: int | None = None) -> None:
        """Store read-only O10 feedback for twist diagnostics. Never drives control."""
        if self.config.twist is None:
            return
        array = np.asarray(positions, dtype=np.float64)
        if array.shape != (10,) or not np.all(np.isfinite(array)):
            return
        self._feedback_positions = array.copy()
        self._feedback_available = False
        self._feedback_theta = math.nan
        self._feedback_axis_deviation = math.nan
        if (
            self.coupling is None
            or self.kinematics is None
            or self._twist_reference is None
        ):
            return
        try:
            full_state = self.coupling.evaluate(array)
            tips = self.kinematics.tip_positions_and_jacobians(
                full_state, self._twist_tip_frames
            )[0]
            state = measure_tripod_state(
                tips,
                self._twist_reference,
                self.config.twist.axis_epsilon,
                self.config.twist.projection_epsilon,
            )
        except Exception:
            return
        if state is None or not math.isfinite(state.theta):
            return
        self._feedback_theta = state.theta
        self._feedback_axis_deviation = state.axis_deviation
        self._feedback_available = True

    def _update_twist_state(self, finger_points, current_lengths, targets) -> None:
        if (
            self._twist_gate is None
            or self._twist_tracker is None
            or targets is None
            or self._stale
        ):
            return
        frozen = [estimator.frozen_length for estimator in self._estimators[:3]]
        if any(value is None for value in frozen):
            return
        scale = sum(float(value) for value in frozen) / 3.0
        points = tuple(finger_points[index][3] for index in range(3))
        valid = all(targets[index] is not None for index in range(3))
        aperture = gate_aperture(points, scale) if valid else None
        extension = gate_extension(points, scale) if valid else None
        self._last_aperture = (
            float(aperture) if aperture is not None else math.nan
        )
        self._last_extension = (
            float(extension) if extension is not None else math.nan
        )
        self._twist_gate.update(aperture, extension, valid)
        if self._twist_gate.just_activated:
            self._twist_reference = None
            self._twist_reference_failure = None
            activated = self._twist_tracker.activate(points)
            self._twist_reference_pending = activated
            if not activated:
                self._twist_reference_failure = "human-reference-invalid"
        if self._twist_gate.just_deactivated:
            self._twist_tracker.deactivate()
            self._twist_reference = None
            self._twist_reference_failure = None
            self._twist_reference_pending = False
            self._feedback_available = False
            self._feedback_theta = math.nan
            self._feedback_axis_deviation = math.nan
        if self._twist_gate.active and self._twist_tracker.active and valid:
            self._twist_tracker.update(points)

    def _latch_twist_reference(self, baseline: np.ndarray) -> str | None:
        if (
            self.config.twist is None
            or self.coupling is None
            or self.kinematics is None
        ):
            return "backend-unavailable"
        try:
            full_state = self.coupling.evaluate(baseline)
            tips = self.kinematics.tip_positions_and_jacobians(
                full_state, self._twist_tip_frames
            )[0]
            reference = build_tripod_reference(
                tips,
                PALM_NORMAL,
                self.config.twist.axis_epsilon,
                self.config.twist.projection_epsilon,
            )
        except Exception:
            reference = None
        failure = None
        if reference is not None and self._twist_tracker is not None:
            if self._twist_tracker.axis is None:
                reference = None
                failure = "human-reference-invalid"
            else:
                human_axis = np.asarray(
                    self.robot_geometry.map_vector(
                        tuple(float(value) for value in self._twist_tracker.axis)
                    ),
                    dtype=np.float64,
                )
                alignment = float(np.dot(human_axis, reference.axis))
                if alignment <= 1e-6:
                    # A sign convention mismatch means the two tripods do not
                    # describe the same screw direction. Refusing to refine is
                    # safer than reinterpreting the operator's accumulated
                    # angle after the fact.
                    reference = None
                    failure = "axis-mismatch"
        self._twist_reference = reference
        self._twist_reference_pending = False
        self._twist_reference_failure = failure
        self._feedback_available = False
        self._feedback_theta = math.nan
        self._feedback_axis_deviation = math.nan
        if reference is not None:
            return None
        return failure or "robot-reference-invalid"

    def _measure_state(self, command: np.ndarray):
        if (
            self.config.twist is None
            or self.coupling is None
            or self.kinematics is None
            or self._twist_reference is None
        ):
            return None
        try:
            full_state = self.coupling.evaluate(np.asarray(command, dtype=np.float64))
            tips = self.kinematics.tip_positions_and_jacobians(
                full_state, self._twist_tip_frames
            )[0]
            return measure_tripod_state(
                tips,
                self._twist_reference,
                self.config.twist.axis_epsilon,
                self.config.twist.projection_epsilon,
            )
        except Exception:
            return None

    def _apply_twist(self, baseline: np.ndarray):
        """Return (command, status, failure, refinement, duration, command_state)."""
        if (
            self.config.twist is None
            or self._twist_gate is None
            or self._twist_tracker is None
        ):
            return baseline, "not-active", None, None, 0.0, None
        if not self._twist_gate.active:
            return baseline, "not-active", None, None, 0.0, None
        if not self._twist_tracker.active:
            return (
                baseline, "fallback-baseline", "human-reference-invalid",
                None, 0.0, self._measure_state(baseline),
            )
        if self._twist_reference is None:
            return (
                baseline, "fallback-baseline",
                self._twist_reference_failure or "robot-reference-invalid",
                None, 0.0, None,
            )
        if not self._twist_tracker.valid:
            return (
                baseline, "fallback-baseline", "human-geometry-invalid",
                None, 0.0, self._measure_state(baseline),
            )
        if self.coupling is None or self.kinematics is None:
            return (
                baseline, "fallback-baseline", "backend-unavailable",
                None, 0.0, self._measure_state(baseline),
            )
        limits = JOINT_LIMITS[self.side]
        lower = np.asarray(
            [limits.lower[index] for index in TRIPOD_ACTIVE_INDICES],
            dtype=np.float64,
        )
        upper = np.asarray(
            [limits.upper[index] for index in TRIPOD_ACTIVE_INDICES],
            dtype=np.float64,
        )
        problem = TripodProblem(
            active_indices=TRIPOD_ACTIVE_INDICES,
            tip_frames=self._twist_tip_frames,
            baseline=np.asarray(baseline, dtype=np.float64).copy(),
            lower=lower,
            upper=upper,
            reference=self._twist_reference,
            target_increment=self._twist_tracker.target_increment,
            length_scale=float(
                np.mean(np.asarray(self.robot_geometry.finger_chain_lengths[:3]))
            ),
            config=self.config.twist,
        )
        started = self._clock()
        try:
            refinement = refine_tripod(problem, self.coupling, self.kinematics)
        except Exception:
            return (
                baseline, "fallback-baseline", "solver-error",
                None, self._clock() - started, self._measure_state(baseline),
            )
        duration = self._clock() - started
        if refinement.applied and refinement.candidate is not None:
            command = np.asarray(baseline, dtype=np.float64).copy()
            command[list(TRIPOD_ACTIVE_INDICES)] = refinement.candidate
            return (
                command, "applied", None, refinement, duration,
                refinement.state,
            )
        return (
            baseline,
            "fallback-baseline",
            refinement.failure or "refinement-rejected",
            refinement,
            duration,
            self._measure_state(baseline),
        )

    def _twist_snapshot(
        self,
        *,
        status: str,
        failure: str | None = None,
        refinement=None,
        command_state=None,
        duration_sec: float = math.nan,
        valid: bool = True,
    ) -> TwistSnapshot | None:
        if (
            self.config.twist is None
            or self._twist_gate is None
            or self._twist_tracker is None
        ):
            return None
        state = command_state
        terms = refinement.terms if refinement is not None else None
        return TwistSnapshot(
            active=self._twist_gate.active,
            gate_aperture=self._last_aperture,
            gate_extension=self._last_extension,
            gate_on_count=self._twist_gate.on_count,
            gate_off_count=self._twist_gate.off_count,
            theta_task=self._twist_tracker.theta_task,
            theta_base=self._twist_tracker.theta_base,
            theta_increment=self._twist_tracker.target_increment,
            theta_robot_cmd=(
                state.theta if state is not None else math.nan
            ),
            theta_robot_fb=self._feedback_theta,
            theta_robot_fb_available=self._feedback_available,
            axis_deviation_cmd_deg=(
                math.degrees(state.axis_deviation) if state is not None else math.nan
            ),
            axis_deviation_fb_deg=(
                math.degrees(self._feedback_axis_deviation)
                if self._feedback_available
                else math.nan
            ),
            axis_deviation_fb_available=self._feedback_available,
            objective_total=terms.total if terms is not None else math.nan,
            objective_rot=terms.rot if terms is not None else math.nan,
            objective_conn=terms.conn if terms is not None else math.nan,
            objective_axis=terms.axis if terms is not None else math.nan,
            objective_pos=terms.pos if terms is not None else math.nan,
            refinement_status=status,
            failure_reason=failure,
            iterations=refinement.iterations if refinement is not None else 0,
            evaluations=refinement.evaluations if refinement is not None else 0,
            solve_duration_sec=duration_sec,
            valid=valid,
        )

    def _reset_twist_episode(self) -> None:
        if self._twist_gate is not None:
            self._twist_gate.active = False
            self._twist_gate.on_count = 0
            self._twist_gate.off_count = 0
            self._twist_gate.just_activated = False
            self._twist_gate.just_deactivated = False
        if self._twist_tracker is not None:
            self._twist_tracker.deactivate()
        self._twist_reference = None
        self._twist_reference_pending = False
        self._twist_reference_failure = None
        self._feedback_available = False
        self._feedback_theta = math.nan
        self._feedback_axis_deviation = math.nan

    def _apply_thumb_adjustments(self, command: np.ndarray) -> np.ndarray:
        roll_gain = self.config.thumb_roll_sensitivity
        abad_gain = self.config.thumb_abad_sensitivity
        adjusted = command.copy()
        limits = JOINT_LIMITS[self.side]
        fixed_thumb_roll = self.config.thumb_roll_fixed_value
        if fixed_thumb_roll is not None:
            adjusted[0] = float(
                np.clip(fixed_thumb_roll, limits.lower[0], limits.upper[0])
            )
        elif not math.isclose(roll_gain, 1.0):
            adjusted[0] = float(
                np.clip(adjusted[0] * roll_gain, limits.lower[0], limits.upper[0])
            )
        fixed_thumb_abad = self.config.thumb_abad_fixed_value
        if fixed_thumb_abad is not None:
            adjusted[1] = float(
                np.clip(fixed_thumb_abad, limits.lower[1], limits.upper[1])
            )
        elif not math.isclose(abad_gain, 1.0):
            adjusted[1] = float(
                np.clip(adjusted[1] * abad_gain, limits.lower[1], limits.upper[1])
            )
        return adjusted

    def _process_recovery(self, frame, current_lengths, targets, *, side_valid):
        decision = self._solve_and_publish(
            frame.received_at_ns, current_lengths, targets, side_valid=side_valid,
            recovery=True,
        )
        current_valid = all(value is not None for value in targets or ())
        candidates_valid = all(decision.has_valid_ik)
        if self._recovery_attempt_start_ns is None:
            self._recovery_attempt_start_ns = frame.received_at_ns
        if current_valid and candidates_valid:
            if self._valid_streak_start_ns is None:
                self._valid_streak_start_ns = frame.received_at_ns
            self._recovery_frames += 1
            duration = (frame.received_at_ns - self._valid_streak_start_ns) / 1e9
            if (
                self._recovery_frames >= self.config.recovery_min_valid_frames
                and duration >= self.config.recovery_min_duration_sec
            ):
                self._stale = False
                self._recovery_frames = 0
                self._recovery_attempt_start_ns = None
                self._valid_streak_start_ns = None
                self._filter.reset_time(frame.received_at_ns)
                return self._solve_and_publish(
                    frame.received_at_ns, current_lengths, targets,
                    side_valid=True, recovery_resume=True,
                )
        else:
            self._recovery_frames = 0
            self._valid_streak_start_ns = None
            duration = 0.0
        if (
            frame.received_at_ns - self._recovery_attempt_start_ns
            > self.config.recovery_confirmation_timeout_sec * 1e9
        ):
            self._recovery_frames = 0
            self._valid_streak_start_ns = None
            self._recovery_attempt_start_ns = None
            return self._decision(
                frame.received_at_ns, side_valid=False,
                current_lengths=current_lengths, targets=None, stale=True,
                solve_executed=decision.solve_executed,
                ik_state=decision.ik_state,
                has_valid_ik=decision.has_valid_ik,
                used_previous_valid_target=decision.used_previous_valid_target,
                residual_available=decision.residual_available,
                normalized_residual=decision.normalized_residual,
                solver_result_code=decision.solver_result_code,
                solver_evaluations=decision.solver_evaluations,
                target_projection_applied=decision.target_projection_applied,
                target_projection_distance_available=(
                    decision.target_projection_distance_available
                ),
                normalized_target_projection_distance=(
                    decision.normalized_target_projection_distance
                ),
                solve_duration_sec=decision.solve_duration_sec,
                recovery_valid_count=0,
                recovery_valid_duration_sec=0.0,
                twist_snapshot=decision.twist,
            )
        return self._decision(
            frame.received_at_ns, side_valid=False, current_lengths=current_lengths,
            targets=None, stale=True,
            solve_executed=decision.solve_executed,
            ik_state=decision.ik_state,
            has_valid_ik=decision.has_valid_ik,
            used_previous_valid_target=decision.used_previous_valid_target,
            residual_available=decision.residual_available,
            normalized_residual=decision.normalized_residual,
            solver_result_code=decision.solver_result_code,
            solver_evaluations=decision.solver_evaluations,
            target_projection_applied=decision.target_projection_applied,
            target_projection_distance_available=(
                decision.target_projection_distance_available
            ),
            normalized_target_projection_distance=(
                decision.normalized_target_projection_distance
            ),
            solve_duration_sec=decision.solve_duration_sec,
            phase_override="recovery-confirming",
            recovery_valid_count=self._recovery_frames,
            recovery_valid_duration_sec=duration,
            twist_snapshot=decision.twist,
        )

    def _solve_and_publish(
        self, stamp_ns, current_lengths, targets, *, side_valid, recovery=False,
        recovery_resume=False,
    ):
        started = self._clock()
        states, has_valid, used_previous, residual_available = [], [], [], []
        projection_applied, projection_available, projection_distances = [], [], []
        residuals, result_codes, evaluations = [], [], []
        committed = [None] * 5
        effective_targets = list(targets or (None,) * 5)
        for index, (target, active_indices) in enumerate(
            zip(targets or (None,) * 5, FINGER_ACTIVE_INDICES)
        ):
            previous = self._last_valid[index]
            if target is None:
                states.append("input-invalid")
                has_valid.append(False if recovery else self._has_valid[index])
                used_previous.append(previous is not None)
                residual_available.append(False)
                residuals.append(float("nan"))
                result_codes.append(None)
                evaluations.append(0)
                projection_applied.append(False)
                projection_available.append(False)
                projection_distances.append(float("nan"))
                committed[index] = previous
                continue
            limits = JOINT_LIMITS[self.side]
            lower = tuple(float(limits.lower[i]) for i in active_indices)
            upper = tuple(float(limits.upper[i]) for i in active_indices)
            problem = FingerProblem(
                active_indices=active_indices,
                tip_frame=tip_link(self.side.value, FINGER_TIP_BASES[index]),
                robot_length=self.robot_geometry.finger_chain_lengths[index],
                target=np.asarray(target, dtype=np.float64),
                lower=np.asarray(lower, dtype=np.float64),
                upper=np.asarray(upper, dtype=np.float64),
            )
            if previous is None:
                initial = (problem.lower + problem.upper) / 2.0
            else:
                initial = np.asarray(previous, dtype=np.float64)
            try:
                result = self.optimizer.solve(problem, initial)
                raw_evidence = validate_candidate(
                    result.candidate, problem, self.coupling, self.kinematics,
                    result.solver_usable, result.result_code, result.evaluations,
                    self.config.ik_residual_thresholds[index],
                )
                evidence = raw_evidence
                applied = False
                witness = None
                if raw_evidence.valid:
                    projection_available.append(True)
                    projection_distances.append(0.0)
                else:
                    witness = build_projection_witness(
                        problem, raw_evidence.active, self.coupling, self.kinematics
                    )
                    projection_available.append(witness.available)
                    projection_distances.append(
                        witness.distance if witness.available else float("nan")
                    )
                    if witness.available:
                        projected_problem = FingerProblem(
                            active_indices=problem.active_indices,
                            tip_frame=problem.tip_frame,
                            robot_length=problem.robot_length,
                            target=witness.target,
                            lower=problem.lower,
                            upper=problem.upper,
                        )
                        projected_evidence = validate_candidate(
                            witness.active, projected_problem, self.coupling,
                            self.kinematics, raw_evidence.solver_usable,
                            raw_evidence.solver_result_code,
                            raw_evidence.evaluations,
                            self.config.ik_residual_thresholds[index],
                        )
                        if projected_evidence.valid:
                            evidence = projected_evidence
                            applied = True
                            effective_targets[index] = tuple(
                                float(value) for value in witness.target
                            )
                projection_applied.append(applied)
            except Exception:
                evidence = CandidateEvidence(None, float("nan"), False, False, -1, 0)
                projection_applied.append(False)
                projection_available.append(False)
                projection_distances.append(float("nan"))
            states.append(
                "valid"
                if evidence.valid
                else "residual-exceeded"
                if np.isfinite(evidence.residual)
                else "solver-error"
            )
            has_valid.append(
                evidence.valid
                if recovery
                else self._has_valid[index] or evidence.valid
            )
            used_previous.append(previous is not None and not evidence.valid)
            residual_available.append(bool(np.isfinite(evidence.residual)))
            residuals.append(evidence.residual)
            result_codes.append(evidence.solver_result_code)
            evaluations.append(evidence.evaluations)
            committed[index] = evidence.active if evidence.valid else previous
            if evidence.valid and not recovery:
                self._last_valid[index] = evidence.active.copy()
                self._has_valid[index] = True
        complete = all(item is not None for item in committed)
        command = None
        command_published = False
        twist_snapshot = self._twist_snapshot(status="not-active", valid=side_valid)
        if complete and side_valid and not recovery:
            baseline = np.concatenate(committed)
            twist_status = "not-active"
            twist_failure = None
            refinement = None
            twist_duration = math.nan
            command_state = None
            gate_active = (
                self.config.twist is not None
                and self._twist_gate is not None
                and self._twist_gate.active
            )
            if gate_active:
                if self._twist_reference_pending:
                    twist_failure = self._latch_twist_reference(baseline)
                if self._twist_reference is None:
                    combined = baseline
                    twist_status = "fallback-baseline"
                    twist_failure = (
                        twist_failure
                        or self._twist_reference_failure
                        or "robot-reference-invalid"
                    )
                else:
                    (
                        combined,
                        twist_status,
                        twist_failure,
                        refinement,
                        twist_duration,
                        command_state,
                    ) = self._apply_twist(baseline)
            else:
                combined = self._apply_thumb_adjustments(baseline)
            twist_snapshot = self._twist_snapshot(
                status=twist_status,
                failure=twist_failure,
                refinement=refinement,
                command_state=command_state,
                duration_sec=twist_duration,
                valid=side_valid,
            )
            if recovery_resume:
                command = self._filter.hold()
                command_published = command is not None
            else:
                command = self._filter.update(combined, stamp_ns)
                command_published = command is not None
        elif self._twist_gate is not None and self._twist_gate.active:
            twist_snapshot = self._twist_snapshot(
                status="fallback-baseline",
                failure="baseline-incomplete",
                valid=side_valid,
            )
        return self._decision(
            stamp_ns, side_valid=side_valid, current_lengths=current_lengths,
            targets=tuple(effective_targets),
            command_published=command_published,
            command_positions=(
                None if command is None else tuple(float(v) for v in command)
            ),
            solve_executed=True, solve_duration_sec=self._clock() - started,
            ik_state=tuple(states), has_valid_ik=tuple(has_valid),
            used_previous_valid_target=tuple(used_previous),
            residual_available=tuple(residual_available),
            normalized_residual=tuple(residuals), solver_result_code=tuple(result_codes),
            solver_evaluations=tuple(evaluations),
            target_projection_applied=tuple(projection_applied),
            target_projection_distance_available=tuple(projection_available),
            normalized_target_projection_distance=tuple(projection_distances),
            stale=self._stale if not recovery_resume else False,
            recovery_valid_count=self._recovery_frames,
            recovery_valid_duration_sec=0.0,
            phase_override=(
                "recovery-resuming" if recovery_resume else
                "recovery-confirming" if recovery else None
            ),
            twist_snapshot=twist_snapshot,
        )

    def _decision(
        self,
        input_stamp_ns: int,
        *,
        side_valid: bool,
        current_lengths: tuple[float | None, ...] | None,
        targets=None,
        stale=False,
        solve_executed=False,
        command_published=False,
        command_positions=None,
        solve_duration_sec=math.nan,
        ik_state=None,
        has_valid_ik=None,
        used_previous_valid_target=None,
        residual_available=None,
        normalized_residual=None,
        solver_result_code=None,
        solver_evaluations=None,
        target_projection_applied=None,
        target_projection_distance_available=None,
        normalized_target_projection_distance=None,
        recovery_valid_count=0,
        recovery_valid_duration_sec=0.0,
        phase_override=None,
        twist_snapshot=None,
    ) -> RetargetingDecision:
        all_frozen = all(estimator.frozen_length is not None for estimator in self._estimators)
        phase = phase_override or (
            "stale" if stale else
            "tracking" if all_frozen and all(self._has_valid) else
            "waiting-first-valid-ik" if all_frozen else "collecting-lengths"
        )
        length_frozen = []
        length_current_valid = []
        for index, estimator in enumerate(self._estimators):
            frozen = estimator.frozen_length
            current = current_lengths[index] if current_lengths is not None else None
            current_valid = current is not None
            if frozen is not None:
                current_valid = current is not None and (
                    abs(current - frozen) / frozen
                    <= self.config.frozen_length_relative_thresholds[index]
                )
                if not side_valid:
                    current_valid = False
            length_frozen.append(frozen is not None)
            length_current_valid.append(current_valid)
        default_ik_state = (
            ("side-invalid",) * 5 if stale or (all_frozen and not side_valid) else
            ("not-run-length-collecting",) * 5 if not all_frozen else
            ("uninitialized",) * 5
        )
        return RetargetingDecision(
            phase=phase,
            side_valid=side_valid,
            all_lengths_frozen=all_frozen,
            command_published=command_published,
            length_frozen=tuple(length_frozen),
            length_current_valid=tuple(length_current_valid),
            targets=targets,
            input_stamp_ns=input_stamp_ns,
            ik_state=tuple(ik_state or default_ik_state),
            has_valid_ik=tuple(has_valid_ik or self._has_valid),
            used_previous_valid_target=tuple(used_previous_valid_target or (False,) * 5),
            residual_available=tuple(residual_available or (False,) * 5),
            normalized_residual=tuple(normalized_residual or (float("nan"),) * 5),
            solver_result_code=tuple(solver_result_code or (None,) * 5),
            solver_evaluations=tuple(solver_evaluations or (0,) * 5),
            target_projection_applied=tuple(target_projection_applied or (False,) * 5),
            target_projection_distance_available=tuple(
                target_projection_distance_available or (False,) * 5
            ),
            normalized_target_projection_distance=tuple(
                normalized_target_projection_distance or (float("nan"),) * 5
            ),
            solve_executed=solve_executed,
            command_stamp_ns=input_stamp_ns if command_published else None,
            command_positions=command_positions,
            stale=stale,
            recovery_valid_count=recovery_valid_count,
            recovery_valid_duration_sec=recovery_valid_duration_sec,
            solve_duration_sec=solve_duration_sec,
            twist=twist_snapshot,
        )
