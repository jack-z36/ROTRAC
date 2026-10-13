"""ROS message conversion kept outside the pure Provider Application."""

from __future__ import annotations

from builtin_interfaces.msg import Time as RosTime
from rokoko_omnihand_msgs.srv import ReadO10ActiveJoints
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import Int16MultiArray

from omnihand_o10_contracts import (
    ACTIVE_JOINT_COUNT,
    ACTIVE_JOINT_NAMES,
    JointError,
    JointFeedback,
    JointSampleTime,
    JointTarget,
    Side,
)

from ..contracts import (
    BackendCode,
    HardwareResponse,
    TACTILE_REGIONS,
    TactileSample,
)

__all__ = [
    "errors_to_message",
    "feedback_to_message",
    "read_response_from_result",
    "tactile_to_message",
    "target_from_message",
]


def _sample_time(value: RosTime) -> JointSampleTime:
    return JointSampleTime(float(value.sec) + float(value.nanosec) * 1e-9)


def target_from_message(side: Side, message: JointState) -> JointTarget:
    """Convert and validate the final command wire shape."""

    if tuple(message.name) != ACTIVE_JOINT_NAMES:
        raise ValueError("command name must use the fixed O10 active-joint order")
    if message.velocity or message.effort:
        raise ValueError("command velocity and effort must be empty")
    if message.header.frame_id:
        raise ValueError("command frame_id must be empty")
    return JointTarget(side, tuple(message.position), _sample_time(message.header.stamp))


def feedback_to_message(feedback: JointFeedback) -> JointState:
    """Convert a validated feedback sample to the fixed 10-position wire form."""

    message = JointState()
    message.header.stamp = _ros_time(feedback.stamp)
    message.position = list(feedback.as_tuple())
    return message


def errors_to_message(errors: JointError) -> Int16MultiArray:
    """Convert a validated error vector to the vendor-wire error words."""

    message = Int16MultiArray()
    message.data = [int(value) for value in errors.as_tuple()]
    return message


def tactile_to_message(sample: TactileSample) -> Image:
    """Pack all seven O10 regions into one little-endian mono16 image.

    The image is a flat, lossless 1x268 tactile vector.  Region order follows
    ``TACTILE_REGIONS``: thumb, index, middle, ring, little, palm, dorsum.
    The O10 source values are uint8, so conversion to mono16 preserves their
    numeric value and writes a zero high byte for every point.
    """

    point_count = sum(length for _, length in TACTILE_REGIONS)
    message = Image()
    message.header.stamp = _ros_time(sample.stamp)
    message.height = 1
    message.width = point_count
    message.encoding = "mono16"
    message.is_bigendian = 0
    message.step = point_count * 2

    payload = bytearray(message.step)
    byte_index = 0
    for region_name, _ in TACTILE_REGIONS:
        for value in getattr(sample, region_name):
            payload[byte_index] = value
            payload[byte_index + 1] = 0
            byte_index += 2
    message.data = bytes(payload)
    return message


def read_response_from_result(
    result: HardwareResponse[JointFeedback],
    response: ReadO10ActiveJoints.Response,
) -> ReadO10ActiveJoints.Response:
    """Map a pure response while retaining ``BLOCKED_EXTERNAL`` in text."""

    response.success = result.success
    response.message = result.message
    if result.success:
        response.result_code = ReadO10ActiveJoints.Response.READ_SUCCESS
        response.sample_stamp = _ros_time(result.value.stamp)
        response.position = list(result.value.as_tuple())
        return response

    response.result_code = _read_result_code(result.code)
    response.sample_stamp = RosTime()
    response.position = [0.0] * ACTIVE_JOINT_COUNT
    return response


def _read_result_code(code: BackendCode) -> int:
    if code is BackendCode.DEVICE_UNAVAILABLE or code is BackendCode.BLOCKED_EXTERNAL:
        return ReadO10ActiveJoints.Response.READ_DEVICE_UNAVAILABLE
    if code is BackendCode.HARDWARE_ERROR:
        return ReadO10ActiveJoints.Response.READ_HARDWARE_ERROR
    if code is BackendCode.INVALID_RESULT:
        return ReadO10ActiveJoints.Response.READ_INVALID_RESULT
    return ReadO10ActiveJoints.Response.READ_INTERNAL_ERROR


def _ros_time(value: JointSampleTime) -> RosTime:
    output = RosTime()
    seconds = int(value.seconds)
    output.sec = seconds
    output.nanosec = int(round((value.seconds - seconds) * 1e9))
    if output.nanosec == 1_000_000_000:
        output.sec += 1
        output.nanosec = 0
    return output
