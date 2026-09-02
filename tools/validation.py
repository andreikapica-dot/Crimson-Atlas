"""Validation tools."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def validate_pois() -> None:
    """Validate POI data integrity."""
    log.info("POI validation tool")


def validate_calibration() -> None:
    """Validate calibration data."""
    log.info("Calibration validation tool")
