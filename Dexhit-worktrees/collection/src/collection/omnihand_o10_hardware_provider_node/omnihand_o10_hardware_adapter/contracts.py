"""Pure results shared by the production Provider boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import operator
from typing import Generic, TypeVar

from omnihand_o10_contracts import JointSampleTime, Side

__all__ = [
    "BackendCode",
    "BLOCKED_EXTERNAL",
    "HardwareResponse",
    "TACTILE_REGIONS",
    "TactileSample",
]


TACTILE_REGIONS = (
    ("thumb", 16),
    ("index", 18),
    ("middle", 18),
    ("ring", 18),
    ("little", 18),
    ("palm", 78),
    ("dorsum", 102),
)


class BackendCode(StrEnum):
    """Machine-readable outcomes at the external hardware boundary."""

    SUCCESS = "SUCCESS"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    DEVICE_UNAVAILABLE = "DEVICE_UNAVAILABLE"
    HARDWARE_ERROR = "HARDWARE_ERROR"
    INVALID_RESULT = "INVALID_RESULT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


BLOCKED_EXTERNAL = BackendCode.BLOCKED_EXTERNAL

T = TypeVar("T")


@dataclass(frozen=True)
class HardwareResponse(Generic[T]):
    """A result that never hides an unavailable external capability."""

    code: BackendCode
    message: str
    value: T | None = None

    @property
    def success(self) -> bool:
        """Whether the operation completed with a usable value."""

        return self.code is BackendCode.SUCCESS

    @classmethod
    def success_result(cls, value: T | None = None, message: str = "success"):
        """Build a successful result for a completed operation."""

        return cls(BackendCode.SUCCESS, message, value)

    @classmethod
    def failure(cls, code: BackendCode, message: str):
        """Build an explicit non-success result without a stale value."""

        if code is BackendCode.SUCCESS:
            raise ValueError("failure result cannot use SUCCESS")
        return cls(code, message, None)


@dataclass(frozen=True)
class TactileSample:
    """One complete O10 1D tactile frame from all seven sensor regions."""

    side: Side
    stamp: JointSampleTime
    thumb: tuple[int, ...]
    index: tuple[int, ...]
    middle: tuple[int, ...]
    ring: tuple[int, ...]
    little: tuple[int, ...]
    palm: tuple[int, ...]
    dorsum: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "side", Side.from_value(self.side))
        if not isinstance(self.stamp, JointSampleTime):
            object.__setattr__(self, "stamp", JointSampleTime(self.stamp))
        for name, expected_length in TACTILE_REGIONS:
            values = tuple(getattr(self, name))
            if len(values) != expected_length:
                raise ValueError(
                    f"{name} tactile region must contain {expected_length} points; "
                    f"got {len(values)}"
                )
            normalized = []
            for index, value in enumerate(values):
                if isinstance(value, bool):
                    raise ValueError(
                        f"{name} tactile point {index} must be an integer in 0..255"
                    )
                try:
                    point = operator.index(value)
                except TypeError as error:
                    raise ValueError(
                        f"{name} tactile point {index} must be an integer in 0..255"
                    ) from error
                if not 0 <= point <= 255:
                    raise ValueError(
                        f"{name} tactile point {index} is outside 0..255: {point}"
                    )
                normalized.append(int(point))
            object.__setattr__(self, name, tuple(normalized))
