"""Production O10 hardware boundary with an explicit external capability gate."""

from .application.provider import O10HardwareProviderApplication
from .contracts import BLOCKED_EXTERNAL, BackendCode, HardwareResponse, TactileSample
from .ports import O10HardwarePort, O10ProviderPort, O10TactilePort

__all__ = [
    "BLOCKED_EXTERNAL",
    "BackendCode",
    "HardwareResponse",
    "O10HardwarePort",
    "O10ProviderPort",
    "O10HardwareProviderApplication",
    "O10TactilePort",
    "TactileSample",
]

__version__ = "0.1.0"
