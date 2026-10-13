"""ROS 2 node that runs the pure O10 control sessions against the wire.

The node is the only place that touches rclpy entities and the wire schema
(ARCHITECTURE A03).  It owns:

* effect execution -- publish commands / control state / error queries, call the
  read-active-joints service, and respond to operator services;
* the asynchronous read-future tracking; and
* the blocking clear_fault round-trips (error-status query then feedback read),
  performed synchronously in the service handler with a ``MultiThreadedExecutor``
  so the provider callbacks keep running while the handler waits.

All state-machine decisions stay inside :class:`ControlSession`; the node never
decides phase, fault, or result codes.
"""

from __future__ import annotations

import threading
import time

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from rokoko_omnihand_msgs.msg import O10ControlState
from rokoko_omnihand_msgs.srv import ControlOperation, ReadO10ActiveJoints
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, Int16MultiArray

from omnihand_o10_contracts import JointFeedback, JointSampleTime, Side

from .adapters.ros_convert import (
    build_command_message,
    build_state_message,
    error_words_to_joint_error,
    joint_state_to_soft_target,
    operation_result_to_response,
    read_response_to_feedback,
    ros_time_to_sample_time,
)
from .application.control_session import ControlSession
from .contracts import (
    CommandPublishFailed,
    CommandSent,
    ErrorStatusReceived,
    FeedbackReceived,
    InvalidErrorStatusReceived,
    InvalidFeedbackReceived,
    OperationResult,
    OperatorClearFaultRequest,
    PublishControlState,
    QueryErrorStatus,
    ReadActiveJointsResult,
    ReadActiveJointsTimeout,
    RequestActiveJointsRead,
    SendJointCommand,
    SoftTargetValue,
    TargetReceived,
    TimeoutCheck,
    Trigger,
)

__all__ = ["O10ControlNode", "main"]

_SIDES_PARAM = "sides"
_EXECUTOR_THREADS_PARAM = "executor_threads"


def _select_sides(value: object) -> tuple[Side, ...]:
    """
    Resolve the ``sides`` parameter into the ordered sides to wire up.
    """
    if value == "both":
        return (Side.LEFT, Side.RIGHT)
    if value == "left":
        return (Side.LEFT,)
    if value == "right":
        return (Side.RIGHT,)
    raise ValueError(
        f"unsupported 'sides' parameter value: {value!r} "
        "(expected both|left|right)"
    )


def _command_qos(command_link_best_effort: bool) -> QoSProfile:
    """
    Historical Reliable depth-10 wire or the E2 best-effort probe link.

    Both endpoints of one command hop must switch together (Reliable pub +
    BestEffort sub is compatible, the reverse is not), which is why each
    node owns both directions of its hops.
    """
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1 if command_link_best_effort else 10,
        reliability=(
            ReliabilityPolicy.BEST_EFFORT
            if command_link_best_effort
            else ReliabilityPolicy.RELIABLE
        ),
        durability=DurabilityPolicy.VOLATILE,
    )


def _config_from_params(node: Node, side: Side) -> dict:
    prefix = f"{side.value}"
    import inspect

    from omnihand_o10_control.contracts import ControlConfig

    fields = [f.name for f in inspect.signature(ControlConfig).parameters.values()]
    values = {}
    for field in fields:
        if field == "side":
            values[field] = side
            continue
        param_name = f"{prefix}.{field}"
        if not node.has_parameter(param_name):
            node.declare_parameter(param_name)
        value = node.get_parameter(param_name).value
        if value is None:
            raise ValueError(f"required O10 control parameter is missing: {param_name}")
        values[field] = value
    return values


class _SideRuntime:
    """Wiring for one logical hand side."""

    def __init__(
        self,
        node: Node,
        side: Side,
        config,
        target_group,
        io_group,
        target_best_effort: bool = False,
        command_link_best_effort: bool = False,
    ):
        self.side = side
        self.config = config
        self.session = ControlSession(config)
        command_qos = _command_qos(command_link_best_effort)
        target_qos = _command_qos(target_best_effort)

        self.command_pub = node.create_publisher(
            JointState, f"/o10/{side.value}/joint_cmd", command_qos
        )
        self.state_pub = node.create_publisher(
            O10ControlState, f"/o10_control/{side.value}/state", 10
        )
        self.error_cmd_pub = node.create_publisher(
            Empty, f"/o10/{side.value}/joint_error_cmd", 10
        )
        self.command_sub = node.create_subscription(
            JointState,
            f"/o10_control/{side.value}/command",
            lambda message: node._on_command(side, message),
            target_qos,
            callback_group=target_group,
        )
        self.feedback_sub = node.create_subscription(
            JointState,
            f"/o10/{side.value}/joint_states",
            lambda message: node._on_joint_states(side, message),
            10,
            callback_group=io_group,
        )
        self.error_sub = node.create_subscription(
            Int16MultiArray,
            f"/o10/{side.value}/joint_error_states",
            lambda message: node._on_joint_error_states(side, message),
            10,
            callback_group=io_group,
        )
        self.read_client = node.create_client(
            ReadO10ActiveJoints,
            f"/o10/{side.value}/read_active_joints",
            callback_group=io_group,
        )

        self.pending_read_future = None
        self.pending_read_deadline: float | None = None

        self.error_lock = threading.Lock()
        self.error_seq = 0
        self.error_payload: tuple[int, ...] | None = None

        state_period_name = f"{side.value}.state_publish_min_period"
        metrics_period_name = f"{side.value}.metrics_log_period"
        latest_target_period_name = f"{side.value}.latest_target_send_period"
        self.state_publish_min_period = max(
            0.0, float(node.declare_parameter(state_period_name, 0.0).value)
        )
        self.metrics_log_period = max(
            0.0, float(node.declare_parameter(metrics_period_name, 0.0).value)
        )
        self.latest_target_send_period = max(
            0.0, float(node.declare_parameter(latest_target_period_name, 0.0).value)
        )
        self.latest_target_lock = threading.Lock()
        self.latest_target_value: SoftTargetValue | None = None
        self.latest_target_received_at: JointSampleTime | None = None
        self.latest_target_received_monotonic: float | None = None
        self.latest_target_sequence = 0
        self.last_target_state_publish_monotonic = 0.0
        self.metrics_lock = threading.Lock()
        self.metrics_counts = {
            "target_callbacks": 0,
            "target_processes": 0,
            "command_publish_attempts": 0,
            "command_publish_success": 0,
            "command_publish_failures": 0,
            "state_publish": 0,
            "state_skip": 0,
            "latest_target_stale_skip": 0,
            "latest_target_missed_ticks": 0,
        }
        self.metrics_previous_counts = dict(self.metrics_counts)
        self.metrics_max = {
            "target_callback_sec": 0.0,
            "command_publish_sec": 0.0,
            "state_publish_sec": 0.0,
            "input_age_sec": 0.0,
        }
        self.metrics_last_log_monotonic = time.monotonic()


class O10ControlNode(Node):
    """Run the two per-side O10 control sessions against the wire graph."""

    def __init__(self, left_config=None, right_config=None, parameter_overrides=None):
        super().__init__(
            "o10_control_node", parameter_overrides=parameter_overrides
        )
        # Target commands, slow I/O, and operator services live in separate
        # mutually-exclusive groups: a fresh teleop target must not queue behind
        # feedback/error polling or a blocking clear_fault handler.
        self._target_group = MutuallyExclusiveCallbackGroup()
        self._io_group = MutuallyExclusiveCallbackGroup()
        self._service_group = MutuallyExclusiveCallbackGroup()
        self.declare_parameter(_SIDES_PARAM, "both")
        selected_sides = _select_sides(self.get_parameter(_SIDES_PARAM).value)
        self._sides: dict[Side, _SideRuntime] = {}
        for side in selected_sides:
            override = left_config if side is Side.LEFT else right_config
            self._sides[side] = self._build_side(side, override)

        for side in selected_sides:
            self._build_services(self._sides[side], "clear_fault")

        for side in selected_sides:
            self._publish_state(side, self._sides[side].session.initial_snapshot(self._ros_now()))

        self._timer = self.create_timer(
            next(iter(self._sides.values())).config.control_check_period,
            self._on_timer,
            callback_group=self._io_group,
        )
        self._latest_target_stop = threading.Event()
        self._latest_target_threads = []
        for side, runtime in self._sides.items():
            if runtime.latest_target_send_period > 0.0:
                thread = threading.Thread(
                    target=self._latest_target_loop,
                    args=(side,),
                    daemon=True,
                    name=f"o10-{side.value}-latest-target",
                )
                thread.start()
                self._latest_target_threads.append(thread)

    def destroy_node(self):
        self._latest_target_stop.set()
        for thread in self._latest_target_threads:
            thread.join(timeout=1.0)
        return super().destroy_node()

    def _latest_target_loop(self, side: Side) -> None:
        runtime = self._sides[side]
        period = runtime.latest_target_send_period
        next_tick = time.monotonic() + period
        while not self._latest_target_stop.wait(
            max(0.0, next_tick - time.monotonic())
        ):
            self._on_latest_target_timer(side)
            next_tick += period
            now = time.monotonic()
            if next_tick <= now:
                missed = int((now - next_tick) / period) + 1
                next_tick += missed * period
                self._metric_add(runtime, "latest_target_missed_ticks", missed)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_side(self, side: Side, override) -> _SideRuntime:
        flag_name = f"{side.value}.command_link_best_effort"
        self.declare_parameter(flag_name, False)
        command_link_best_effort = bool(
            self.get_parameter(flag_name).value
        )
        target_flag_name = f"{side.value}.target_best_effort"
        target_best_effort = bool(
            self.declare_parameter(
                target_flag_name, command_link_best_effort
            ).value
        )
        if override is not None:
            config = override
        else:
            from omnihand_o10_control.contracts import ControlConfig

            config = ControlConfig(**_config_from_params(self, side))
        return _SideRuntime(
            self,
            side,
            config,
            self._target_group,
            self._io_group,
            target_best_effort,
            command_link_best_effort,
        )

    def _build_services(self, runtime: _SideRuntime, operation: str) -> None:
        node = self
        self.create_service(
            ControlOperation,
            f"/o10_control/{runtime.side.value}/{operation}",
            lambda request, response, r=runtime, op=operation: self._on_operation(
                r, op, request, response
            ),
            callback_group=self._service_group,
        )

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    def _ros_now(self) -> JointSampleTime:
        return JointSampleTime(self.get_clock().now().nanoseconds * 1e-9)

    def _mono_now(self) -> float:
        return time.monotonic()

    def _stamp_now(self):
        return self.get_clock().now().to_msg()

    # ------------------------------------------------------------------
    # Subscription callbacks (non-blocking entry points)
    # ------------------------------------------------------------------

    def _on_command(self, side: Side, message: JointState) -> None:
        runtime = self._sides[side]
        callback_start = self._mono_now()
        self._metric_count(runtime, "target_callbacks")
        received_at = self._ros_now()
        received_monotonic = self._mono_now()
        value = joint_state_to_soft_target(side, message, received_at)
        if runtime.latest_target_send_period > 0.0:
            with runtime.latest_target_lock:
                runtime.latest_target_value = value
                runtime.latest_target_received_at = received_at
                runtime.latest_target_received_monotonic = received_monotonic
                runtime.latest_target_sequence += 1
        else:
            self._process_target_value(
                runtime,
                value,
                received_at,
                received_monotonic,
                received_at,
                self._mono_now(),
            )
        self._metric_max(
            runtime, "target_callback_sec", self._mono_now() - callback_start
        )

    def _on_latest_target_timer(self, side: Side) -> None:
        runtime = self._sides[side]
        with runtime.latest_target_lock:
            value = runtime.latest_target_value
            received_at = runtime.latest_target_received_at
            received_monotonic = runtime.latest_target_received_monotonic
        if value is None or received_at is None or received_monotonic is None:
            return

        ros_now = self._ros_now()
        monotonic_now = self._mono_now()
        if not self._latest_target_is_fresh(
            runtime, value, ros_now, monotonic_now, received_monotonic
        ):
            self._metric_count(runtime, "latest_target_stale_skip")
            return

        self._process_target_value(
            runtime,
            value,
            received_at,
            received_monotonic,
            ros_now,
            monotonic_now,
        )

    def _latest_target_is_fresh(
        self,
        runtime: _SideRuntime,
        value: SoftTargetValue,
        ros_now: JointSampleTime,
        monotonic_now: float,
        received_monotonic: float,
    ) -> bool:
        receive_age = monotonic_now - received_monotonic
        if (
            receive_age < 0.0
            or receive_age > runtime.config.target_receive_stale_timeout
        ):
            return False
        if value.input_stamp is None:
            return True
        input_age = ros_now.seconds - value.input_stamp.seconds
        return (
            input_age >= 0.0
            and input_age <= runtime.config.target_input_stale_timeout
        )

    def _process_target_value(
        self,
        runtime: _SideRuntime,
        value: SoftTargetValue,
        received_at: JointSampleTime,
        target_received_monotonic: float,
        ros_now: JointSampleTime,
        monotonic_now: float,
    ) -> None:
        self._metric_count(runtime, "target_processes")
        if value.input_stamp is not None:
            self._metric_max(
                runtime, "input_age_sec", ros_now.seconds - value.input_stamp.seconds
            )
        effects = runtime.session.on_target(
            TargetReceived(
                value,
                received_at,
                monotonic_now,
                ros_now,
                target_received_monotonic,
            )
        )
        self._apply_effects(runtime, effects, response=None)

    def _on_joint_states(self, side: Side, message: JointState) -> None:
        runtime = self._sides[side]
        ros_now = self._ros_now()
        mono_now = self._mono_now()
        try:
            feedback = JointFeedback(
                side=side,
                values=tuple(float(value) for value in message.position),
                stamp=ros_time_to_sample_time(message.header.stamp),
            )
        except (TypeError, ValueError) as error:
            effects = runtime.session.on_invalid_feedback(
                InvalidFeedbackReceived(side, str(error), ros_now, mono_now)
            )
        else:
            effects = runtime.session.on_feedback(
                FeedbackReceived(feedback, ros_now, mono_now)
            )
        self._apply_effects(runtime, effects, response=None)

    def _on_joint_error_states(self, side: Side, message: Int16MultiArray) -> None:
        runtime = self._sides[side]
        ros_now = self._ros_now()
        mono_now = self._mono_now()
        with runtime.error_lock:
            try:
                payload = tuple(int(value) & 0xFFFF for value in message.data)
                runtime.error_payload = (
                    payload if len(payload) == 10 else None
                )
            except (TypeError, ValueError):
                runtime.error_payload = None
            runtime.error_seq += 1

        if runtime.session.clear_fault_in_progress:
            return
        try:
            error = error_words_to_joint_error(side, message, ros_now)
        except ValueError as error:
            effects = runtime.session.on_invalid_error_status(
                InvalidErrorStatusReceived(
                    side, str(error), ros_now, mono_now
                )
            )
        else:
            effects = runtime.session.on_error_status(
                ErrorStatusReceived(error, ros_now, mono_now)
            )
        self._apply_effects(runtime, effects, response=None)

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    def _on_operation(self, runtime: _SideRuntime, operation: str, request, response):
        ros_now = self._ros_now()
        effects = runtime.session.on_clear_fault_request(
            OperatorClearFaultRequest(self._mono_now(), ros_now)
        )
        self._apply_effects(runtime, effects, response=response)
        return response

    # ------------------------------------------------------------------
    # Timer (periodic control check + read-future reaping)
    # ------------------------------------------------------------------

    def _on_timer(self) -> None:
        for side in self._sides:
            runtime = self._sides[side]
            effects = runtime.session.check_timeouts(
                TimeoutCheck(self._mono_now(), self._ros_now())
            )
            self._apply_effects(runtime, effects, response=None)
            self._reap_read_future(runtime)
            self._maybe_log_metrics(runtime)

    def _reap_read_future(self, runtime: _SideRuntime) -> None:
        future = runtime.pending_read_future
        if future is None:
            return
        mono_now = self._mono_now()
        ros_now = self._ros_now()
        if future.done():
            runtime.pending_read_future = None
            try:
                result = future.result()
            except Exception:
                result = None
            feedback = (
                read_response_to_feedback(runtime.side, result)
                if result is not None
                else None
            )
            effects = runtime.session.on_read_result(
                ReadActiveJointsResult(
                    feedback is not None,
                    feedback,
                    ros_now,
                    mono_now,
                )
            )
            self._apply_effects(runtime, effects, response=None)
        elif (
            runtime.pending_read_deadline is not None
            and mono_now > runtime.pending_read_deadline
        ):
            runtime.pending_read_future = None
            effects = runtime.session.on_read_timeout(
                ReadActiveJointsTimeout(mono_now)
            )
            self._apply_effects(runtime, effects, response=None)

    # ------------------------------------------------------------------
    # Effect execution
    # ------------------------------------------------------------------

    def _apply_effects(
        self, runtime: _SideRuntime, effects, response
    ) -> None:
        for effect in effects:
            if isinstance(effect, PublishControlState):
                self._publish_state(runtime.side, effect.state)
            elif isinstance(effect, SendJointCommand):
                self._send_command(runtime, effect)
            elif isinstance(effect, QueryErrorStatus):
                if response is not None:
                    self._clear_fault_error_query(runtime, response)
                else:
                    runtime.error_cmd_pub.publish(Empty())
            elif isinstance(effect, RequestActiveJointsRead):
                if response is not None:
                    self._clear_fault_read(runtime, response)
                else:
                    self._start_read(runtime)
            elif isinstance(effect, OperationResult):
                if response is not None:
                    self._fill_response(response, effect)

    def _send_command(self, runtime: _SideRuntime, effect: SendJointCommand) -> None:
        message = build_command_message(effect.command)
        ros_now = self._ros_now()
        self._metric_count(runtime, "command_publish_attempts")
        publish_start = self._mono_now()
        try:
            runtime.command_pub.publish(message)
        except Exception:
            self._metric_count(runtime, "command_publish_failures")
            effects = runtime.session.on_command_publish_failed(
                CommandPublishFailed(ros_now, self._mono_now())
            )
        else:
            publish_duration = self._mono_now() - publish_start
            self._metric_count(runtime, "command_publish_success")
            self._metric_max(runtime, "command_publish_sec", publish_duration)
            if runtime.metrics_log_period > 0.0 and publish_duration >= 0.02:
                self.get_logger().warning(
                    f"{runtime.side.value} joint_cmd publish took "
                    f"{publish_duration * 1000.0:.1f} ms"
                )
            effects = runtime.session.on_command_sent(
                CommandSent(effect.command, ros_now, self._mono_now())
            )
        self._apply_effects(runtime, effects, response=None)

    def _publish_state(self, side: Side, state) -> None:
        runtime = self._sides[side]
        if self._skip_target_success_state(runtime, state):
            self._metric_count(runtime, "state_skip")
            return
        publish_start = self._mono_now()
        runtime.state_pub.publish(build_state_message(state, self._stamp_now()))
        self._metric_count(runtime, "state_publish")
        self._metric_max(runtime, "state_publish_sec", self._mono_now() - publish_start)

    def _skip_target_success_state(self, runtime: _SideRuntime, state) -> bool:
        period = runtime.state_publish_min_period
        if (
            period <= 0.0
            or state.trigger is not Trigger.TARGET_PROCESSED
            or not state.command_published
        ):
            return False
        now = self._mono_now()
        if now - runtime.last_target_state_publish_monotonic < period:
            return True
        runtime.last_target_state_publish_monotonic = now
        return False

    def _metric_count(self, runtime: _SideRuntime, name: str) -> None:
        self._metric_add(runtime, name, 1)

    def _metric_add(self, runtime: _SideRuntime, name: str, count: int) -> None:
        if runtime.metrics_log_period <= 0.0:
            return
        with runtime.metrics_lock:
            runtime.metrics_counts[name] += int(count)

    def _metric_max(self, runtime: _SideRuntime, name: str, value: float) -> None:
        if runtime.metrics_log_period <= 0.0:
            return
        with runtime.metrics_lock:
            runtime.metrics_max[name] = max(runtime.metrics_max[name], float(value))

    def _maybe_log_metrics(self, runtime: _SideRuntime) -> None:
        period = runtime.metrics_log_period
        if period <= 0.0:
            return
        now = self._mono_now()
        if now - runtime.metrics_last_log_monotonic < period:
            return
        with runtime.metrics_lock:
            elapsed = now - runtime.metrics_last_log_monotonic
            counts = dict(runtime.metrics_counts)
            previous = dict(runtime.metrics_previous_counts)
            maximums = dict(runtime.metrics_max)
            runtime.metrics_previous_counts = counts
            runtime.metrics_max = {name: 0.0 for name in runtime.metrics_max}
            runtime.metrics_last_log_monotonic = now
        if elapsed <= 0.0:
            return

        def rate(name: str) -> float:
            return (counts[name] - previous[name]) / elapsed

        self.get_logger().info(
            f"{runtime.side.value} metrics: "
            f"target_cb_hz={rate('target_callbacks'):.1f}, "
            f"target_process_hz={rate('target_processes'):.1f}, "
            f"joint_cmd_hz={rate('command_publish_success'):.1f}, "
            f"state_pub_hz={rate('state_publish'):.1f}, "
            f"state_skip_hz={rate('state_skip'):.1f}, "
            f"latest_stale_skip_hz={rate('latest_target_stale_skip'):.1f}, "
            f"latest_missed_tick_hz={rate('latest_target_missed_ticks'):.1f}, "
            f"target_cb_max_ms={maximums['target_callback_sec'] * 1000.0:.1f}, "
            f"joint_publish_max_ms={maximums['command_publish_sec'] * 1000.0:.1f}, "
            f"state_publish_max_ms={maximums['state_publish_sec'] * 1000.0:.1f}, "
            f"input_age_max_ms={maximums['input_age_sec'] * 1000.0:.1f}"
        )

    def _fill_response(self, response, result: OperationResult) -> None:
        message = build_state_message(result.state, self._stamp_now())
        filled = operation_result_to_response(result, message)
        response.success = filled.success
        response.result_code = filled.result_code
        response.message = filled.message
        response.state = filled.state

    # ------------------------------------------------------------------
    # Async read (normal initialisation)
    # ------------------------------------------------------------------

    def _start_read(self, runtime: _SideRuntime) -> None:
        if (
            runtime.pending_read_future is not None
            and not runtime.pending_read_future.done()
        ):
            return
        if not runtime.read_client.service_is_ready():
            return
        request = ReadO10ActiveJoints.Request()
        runtime.pending_read_future = runtime.read_client.call_async(request)
        runtime.pending_read_deadline = (
            self._mono_now() + runtime.config.read_service_timeout
        )

    # ------------------------------------------------------------------
    # Blocking clear_fault round-trips (service-handler context only)
    # ------------------------------------------------------------------

    def _clear_fault_error_query(self, runtime: _SideRuntime, response) -> None:
        timeout = runtime.config.clear_fault_error_timeout
        with runtime.error_lock:
            seq0 = runtime.error_seq
        runtime.error_cmd_pub.publish(Empty())
        ok, bits = self._wait_error_status(runtime, seq0, timeout)
        effects = runtime.session.on_clear_fault_error_query(
            ok, bits, self._mono_now(), self._ros_now()
        )
        self._apply_effects(runtime, effects, response=response)

    def _wait_error_status(
        self, runtime: _SideRuntime, seq0: int, timeout: float
    ) -> tuple[bool, tuple[int, ...] | None]:
        with runtime.error_lock:
            seq0 = runtime.error_seq
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with runtime.error_lock:
                if runtime.error_seq > seq0:
                    return True, runtime.error_payload
            time.sleep(0.001)
        return False, None

    def _clear_fault_read(self, runtime: _SideRuntime, response) -> None:
        timeout = runtime.config.clear_fault_read_timeout
        completed, feedback = self._blocking_read(runtime, timeout)
        effects = runtime.session.on_clear_fault_read(
            completed, feedback, self._mono_now(), self._ros_now()
        )
        self._apply_effects(runtime, effects, response=response)

    def _blocking_read(
        self, runtime: _SideRuntime, timeout: float
    ) -> tuple[bool, JointFeedback | None]:
        if not runtime.read_client.service_is_ready():
            return False, None
        request = ReadO10ActiveJoints.Request()
        future = runtime.read_client.call_async(request)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not future.done():
            time.sleep(0.001)
        if not future.done():
            return False, None
        try:
            result = future.result()
        except Exception:
            return False, None
        if result is None or not result.success:
            return False, None
        return True, read_response_to_feedback(runtime.side, result)


def main(args=None):
    """Run the O10 control node with a configurable ROS executor."""
    rclpy.init(args=args)
    node = O10ControlNode()
    executor_threads = int(
        node.declare_parameter(_EXECUTOR_THREADS_PARAM, 4).value
    )
    executor = (
        SingleThreadedExecutor()
        if executor_threads <= 1
        else MultiThreadedExecutor(num_threads=executor_threads)
    )
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.remove_node(node)
        node.destroy_node()
        executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()
