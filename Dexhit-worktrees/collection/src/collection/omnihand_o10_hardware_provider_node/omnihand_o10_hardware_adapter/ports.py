"""The pure Application/Port boundary for O10 hardware operations."""

from __future__ import annotations

from typing import Protocol

from omnihand_o10_contracts import JointError, JointFeedback, JointTarget

from .contracts import HardwareResponse, TactileSample

__all__ = ["O10HardwarePort", "O10ProviderPort", "O10TactilePort"]


class O10HardwarePort(Protocol):
    """Four control-safety capabilities shared by all O10 Providers.

    Implementations are selected by composition.  The boundary contains no
    ROS objects and no external library handles; each read is an operation,
    not a request to return a previously observed cache entry.
    """

    def send_command(self, command: JointTarget) -> HardwareResponse[None]:
        """Forward one already validated final position command."""

        ...

    def read_feedback(self) -> HardwareResponse[JointFeedback]:
        """Return a current feedback sample when the backend supports it."""

        ...

    def query_errors(self) -> HardwareResponse[JointError]:
        """Trigger and return one current error-status query."""

        ...

    def read_active_joints(self) -> HardwareResponse[JointFeedback]:
        """Perform one new no-motion active-joint read."""

        ...


class O10TactilePort(Protocol):
    """Read-only vendor tactile capability outside the control safety Port."""

    def read_tactile(self) -> HardwareResponse[TactileSample]:
        """Read one complete raw O10 tactile frame."""

        ...


class O10ProviderPort(O10HardwarePort, O10TactilePort, Protocol):
    """Combined production Provider boundary used by the hardware Adapter."""

    pass
