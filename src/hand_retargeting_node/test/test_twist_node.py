"""ROS graph tests for the TwistState wire and read-only feedback."""

import math
import time
from types import SimpleNamespace

from geometry_msgs.msg import Point
from hand_retargeting import node as node_module
from hand_retargeting.core.normalization import RobotHandGeometry
from omnihand_o10_contracts import ACTIVE_JOINT_NAMES, Side
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rokoko_omnihand_msgs.msg import RawHandFrame, TwistState
from sensor_msgs.msg import JointState


class FakeCoupling:
    def evaluate(self, active):
        import numpy as np

        values = np.asarray(active, dtype=np.float64)
        full = np.zeros(16, dtype=np.float64)
        full[:10] = values
        return full

    def jacobian(self, active):
        import numpy as np

        result = np.zeros((16, 10), dtype=np.float64)
        result[:10, :10] = np.eye(10)
        return result


class FakeTripodKinematics:
    def __init__(self):
        import numpy as np

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
        import numpy as np

        index = self._index(tip_frame)
        tip = self.base[index] + self.matrix[index] @ np.asarray(
            full_q, dtype=np.float64
        )
        return tip, self.matrix[index]

    def tip_positions_and_jacobians(self, full_q, tip_frames):
        import numpy as np

        positions = []
        jacobians = []
        for frame in tip_frames:
            position, jacobian = self.tip_position_and_jacobian(full_q, frame)
            positions.append(position)
            jacobians.append(jacobian)
        return np.stack(positions), np.stack(jacobians)


class FakeOptimizer:
    def __init__(self, *_args, **_kwargs):
        pass

    def solve(self, problem, initial):
        import numpy as np

        class Result:
            pass

        result = Result()
        result.candidate = np.zeros(len(problem.active_indices), dtype=np.float64)
        result.solver_usable = True
        result.result_code = 0
        result.evaluations = 1
        return result


def _geometry():
    return RobotHandGeometry(
        finger_roots=tuple((float(index), 0.0, 0.0) for index in range(5)),
        finger_chain_lengths=(2.0, 3.0, 4.0, 5.0, 6.0),
        direction_mapping=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    )


def _overrides(**changes):
    values = {
        "palm_y_epsilon": 1e-6,
        "palm_x_epsilon": 1e-6,
        "finger_length_epsilon": 1e-6,
        "length_window_size": 3,
        "stable_window_count": 2,
        "length_nmad_thresholds": [0.01] * 5,
        "frozen_length_relative_thresholds": [0.10] * 5,
        "ik_residual_thresholds": [100.0] * 5,
        "ik_max_evaluations": 100,
        "ik_max_time_sec": 0.02,
        "smooth_time_constants": [0.005] * 10,
        "stale_timeout_sec": 0.5,
        "recovery_min_valid_frames": 3,
        "recovery_min_duration_sec": 0.1,
        "recovery_confirmation_timeout_sec": 0.5,
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
        "twist_gradient_tolerance": 1e-6,
        "twist_axis_epsilon": 1e-6,
        "twist_projection_epsilon": 1e-4,
        "twist_axis_deviation_limit_deg": 60.0,
    }
    values.update(changes)
    return [Parameter(name, value=value) for name, value in values.items()]


def _raw(side, *, stamp_ns=123):
    suffixes = (
        "Hand",
        "ThumbProximal", "ThumbMedial", "ThumbDistal", "ThumbTip",
        "IndexProximal", "IndexMedial", "IndexDistal", "IndexTip",
        "MiddleProximal", "MiddleMedial", "MiddleDistal", "MiddleTip",
        "RingProximal", "RingMedial", "RingDistal", "RingTip",
        "LittleProximal", "LittleMedial", "LittleDistal", "LittleTip",
    )
    roots_x = (0.8, 0.6, 0.2, -0.2, -0.6)
    positions = [(0.0, 0.0, 0.0)]
    for root_x in roots_x:
        positions.extend(
            [
                (root_x, 1.0, 0.0),
                (root_x, 1.4, 0.0),
                (root_x, 1.8, 0.0),
                (root_x, 2.2, 0.0),
            ]
        )
    positions[4] = (0.4, 2.0, 0.2)
    message = RawHandFrame()
    message.header.stamp.sec = stamp_ns // 1_000_000_000
    message.header.stamp.nanosec = stamp_ns % 1_000_000_000
    message.node_names = [side.value + suffix for suffix in suffixes]
    message.positions = [Point(x=x, y=y, z=z) for x, y, z in positions]
    return message


def _spin_until(executor, predicate, timeout_sec=2.0):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)
        if predicate():
            return True
    return predicate()


@pytest.fixture
def twist_graph(monkeypatch):
    monkeypatch.setattr(node_module, "load_robot_geometry", lambda side: _geometry())
    monkeypatch.setattr(
        node_module, "load_runtime_assets",
        lambda side: SimpleNamespace(coupling_model=object()),
    )
    monkeypatch.setattr(
        node_module, "load_pinocchio_kinematics",
        lambda assets, side: FakeTripodKinematics(),
    )
    monkeypatch.setattr(
        node_module.CouplingModel, "from_mjcf",
        staticmethod(lambda assets: FakeCoupling()),
    )
    monkeypatch.setattr(node_module, "NloptSlsqpOptimizer", FakeOptimizer)
    rclpy.init()
    retargeter = node_module.HandRetargetingNode(
        parameter_overrides=_overrides()
    )
    observer = Node("twist_state_graph_test_observer")
    executor = SingleThreadedExecutor()
    executor.add_node(retargeter)
    executor.add_node(observer)
    try:
        yield retargeter, observer, executor
    finally:
        executor.remove_node(observer)
        executor.remove_node(retargeter)
        observer.destroy_node()
        retargeter.destroy_node()
        executor.shutdown()
        rclpy.shutdown()


def _collect(observer, side):
    messages = []
    observer.create_subscription(
        TwistState,
        f"/hand_retargeting/{side}/twist_state",
        messages.append,
        10,
    )
    return messages


def test_twist_state_is_published_with_unavailable_fields_as_nan(twist_graph):
    _, observer, executor = twist_graph
    messages = _collect(observer, "left")
    publisher = observer.create_publisher(RawHandFrame, "/rokoko/left/raw_hand", 10)
    publisher.publish(_raw(Side.LEFT, stamp_ns=time.time_ns()))
    assert _spin_until(executor, lambda: bool(messages))
    state = messages[-1]
    assert state.side == "left"
    assert state.valid is True
    assert state.active is False
    assert state.refinement_status == TwistState.REFINEMENT_NOT_ACTIVE
    assert state.failure_reason == TwistState.FAILURE_NONE
    assert state.theta_task == pytest.approx(0.0)
    assert state.theta_base == pytest.approx(0.0)
    assert state.theta_increment == pytest.approx(0.0)
    assert math.isnan(state.theta_robot_cmd)
    assert state.theta_robot_fb_available is False
    assert math.isnan(state.theta_robot_fb)
    assert state.axis_deviation_fb_available is False
    assert math.isnan(state.axis_deviation_fb_deg)
    assert math.isnan(state.objective_total)
    assert math.isnan(state.objective_rot)
    assert math.isnan(state.objective_conn)
    assert math.isnan(state.objective_axis)
    assert math.isnan(state.objective_pos)
    assert math.isnan(state.solve_duration_sec)


def test_twist_state_activates_and_reports_refinement(twist_graph):
    _, observer, executor = twist_graph
    messages = _collect(observer, "left")
    publisher = observer.create_publisher(RawHandFrame, "/rokoko/left/raw_hand", 10)
    base = time.time_ns()
    for index in range(7):
        expected = len(messages) + 1
        publisher.publish(_raw(Side.LEFT, stamp_ns=base + index * 100_000_000))
        assert _spin_until(executor, lambda: len(messages) >= expected)
    state = messages[-1]
    assert state.active is True
    assert state.refinement_status == TwistState.REFINEMENT_APPLIED
    assert state.failure_reason == TwistState.FAILURE_NONE
    assert 0.0 < state.gate_aperture < 0.45
    assert state.gate_extension > 0.5
    assert math.isfinite(state.objective_total)
    assert state.objective_total == pytest.approx(
        state.objective_rot
        + state.objective_conn
        + state.objective_axis
        + state.objective_pos
    )
    assert math.isfinite(state.theta_robot_cmd)
    assert state.iterations >= 1
    assert state.evaluations >= 1


def test_twist_state_reports_read_only_feedback(twist_graph):
    _, observer, executor = twist_graph
    messages = _collect(observer, "left")
    publisher = observer.create_publisher(RawHandFrame, "/rokoko/left/raw_hand", 10)
    feedback = observer.create_publisher(JointState, "/o10/left/joint_states", 10)
    base = time.time_ns()
    for index in range(7):
        expected = len(messages) + 1
        publisher.publish(_raw(Side.LEFT, stamp_ns=base + index * 100_000_000))
        assert _spin_until(executor, lambda: len(messages) >= expected)
    assert messages[-1].theta_robot_fb_available is False

    message = JointState()
    message.name = list(ACTIVE_JOINT_NAMES)
    message.position = [0.0] * len(ACTIVE_JOINT_NAMES)
    feedback.publish(message)
    # Let the feedback subscription run before the next raw frame; the node is
    # event-driven, so no raw frame is required for the read-only update.
    for _ in range(5):
        executor.spin_once(timeout_sec=0.02)
    publisher.publish(_raw(Side.LEFT, stamp_ns=base + 700_000_000))
    expected = len(messages) + 1
    assert _spin_until(executor, lambda: len(messages) >= expected)
    state = messages[-1]
    assert state.theta_robot_fb_available is True
    assert math.isfinite(state.theta_robot_fb)
    assert state.axis_deviation_fb_available is True
    assert math.isfinite(state.axis_deviation_fb_deg)


def test_twist_state_is_published_for_both_sides(twist_graph):
    _, observer, executor = twist_graph
    left_messages = _collect(observer, "left")
    right_messages = _collect(observer, "right")
    left = observer.create_publisher(RawHandFrame, "/rokoko/left/raw_hand", 10)
    right = observer.create_publisher(RawHandFrame, "/rokoko/right/raw_hand", 10)
    left.publish(_raw(Side.LEFT, stamp_ns=time.time_ns()))
    right.publish(_raw(Side.RIGHT, stamp_ns=time.time_ns()))
    assert _spin_until(
        executor, lambda: bool(left_messages) and bool(right_messages)
    )
    assert left_messages[-1].side == "left"
    assert right_messages[-1].side == "right"
    assert left_messages[-1].active is False
    assert right_messages[-1].active is False


def test_missing_twist_parameter_fails_startup(monkeypatch):
    monkeypatch.setattr(node_module, "load_robot_geometry", lambda side: _geometry())
    monkeypatch.setattr(
        node_module, "load_runtime_assets",
        lambda side: SimpleNamespace(coupling_model=object()),
    )
    monkeypatch.setattr(
        node_module, "load_pinocchio_kinematics",
        lambda assets, side: FakeTripodKinematics(),
    )
    monkeypatch.setattr(
        node_module.CouplingModel, "from_mjcf",
        staticmethod(lambda assets: FakeCoupling()),
    )
    monkeypatch.setattr(node_module, "NloptSlsqpOptimizer", FakeOptimizer)
    overrides = [
        parameter
        for parameter in _overrides()
        if parameter.name != "twist_weight_rot"
    ]
    rclpy.init()
    try:
        with pytest.raises(ValueError, match="twist_weight_rot"):
            node_module.HandRetargetingNode(parameter_overrides=overrides)
    finally:
        rclpy.shutdown()


def test_stale_publishes_an_invalid_twist_state(twist_graph):
    _, observer, executor = twist_graph
    messages = _collect(observer, "left")
    publisher = observer.create_publisher(RawHandFrame, "/rokoko/left/raw_hand", 10)
    publisher.publish(_raw(Side.LEFT, stamp_ns=time.time_ns()))
    assert _spin_until(executor, lambda: bool(messages))
    assert messages[-1].valid is True

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)
        if messages[-1].valid is False:
            break
    assert messages[-1].valid is False
    assert messages[-1].active is False
