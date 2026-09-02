"""Process state enum for Crimson Atlas memory engine."""

from __future__ import annotations

from enum import Enum


class ProcessState(Enum):
    """States for the game process connection."""

    GAME_NOT_RUNNING = "game_not_running"
    ATTACHING = "attaching"
    ATTACHED = "attached"
    UNSUPPORTED_BUILD = "unsupported_build"
    ERROR = "error"
