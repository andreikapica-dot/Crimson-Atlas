"""Memory engine package for Crimson Atlas."""

from __future__ import annotations

from memory.state import ProcessState
from memory.types import (
    HookInfo,
    PlayerPosition,
    ScanResult,
    SignatureSet,
)

__all__ = [
    "ProcessState",
    "SignatureSet",
    "HookInfo",
    "ScanResult",
    "PlayerPosition",
]
