"""Canonical AOB pattern parser and validator.

This module provides the single entry point for normalizing AOB signatures
before they are used in memory scanning.

Supported inputs:
- bytes: used as-is
- str: hex string, optionally space-separated, e.g. "0F 28 C6" or "0F28C6"
- wildcard bytes: use ``??`` or ``00`` as wildcard in string form

The canonical output is a tuple:
    (pattern_bytes: bytes, mask: bytes | None)

If the pattern contains no wildcards, mask is None and the pattern is used
as plain bytes.

This module is the ONLY place where string-to-bytes conversion happens.
All other modules must receive bytes from here.
"""

from __future__ import annotations

import logging
import re
from typing import Tuple

log = logging.getLogger(__name__)

# Compiled regex cache for wildcard patterns
_regex_cache: dict[bytes, re.Pattern] = {}


class AOBParseError(Exception):
    """Raised when an AOB pattern string cannot be parsed."""
    pass


def normalize_pattern(pattern: bytes | str) -> bytes:
    """Normalize an AOB pattern to bytes.

    Args:
        pattern: bytes or hex string (with or without spaces).

    Returns:
        bytes object.

    Raises:
        AOBParseError: If the string cannot be parsed.
    """
    if isinstance(pattern, bytes):
        return bytes(pattern)
    if not isinstance(pattern, str):
        raise AOBParseError(
            f"Pattern must be bytes or str, got {type(pattern).__name__}"
        )
    cleaned = re.sub(r"[\s\-_,;]+", "", pattern)
    if len(cleaned) % 2 != 0:
        raise AOBParseError(
            f"Hex string must have even length: {pattern!r}"
        )
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise AOBParseError(f"Invalid hex in pattern {pattern!r}: {exc}") from exc


def parse_pattern(pattern: bytes | str) -> Tuple[bytes, bytes | None]:
    """Parse an AOB pattern into canonical (pattern_bytes, mask).

    Wildcard rules:
    - In a bytes input: byte 0x00 is treated as a wildcard.
    - In a str input: ``??`` or ``00`` are treated as wildcards.

    Args:
        pattern: bytes or str pattern.

    Returns:
        Tuple of (pattern_bytes, mask).
        mask is None if there are no wildcards.
        Otherwise mask is a bytes object where 0x00 means wildcard,
        0xFF means match literally.

    Raises:
        AOBParseError: If the pattern cannot be parsed.
    """
    if isinstance(pattern, bytes):
        # Check for wildcards (0x00 bytes)
        if b"\x00" in pattern:
            mask = bytes(0xFF if b != 0x00 else 0x00 for b in pattern)
            return pattern, mask
        return pattern, None

    if not isinstance(pattern, str):
        raise AOBParseError(
            f"Pattern must be bytes or str, got {type(pattern).__name__}"
        )

    # Parse string pattern
    tokens = re.split(r"[\s]+", pattern.strip())
    byte_list = []
    mask_list = []
    has_wildcard = False

    for token in tokens:
        if not token:
            continue
        token_upper = token.upper()
        if token_upper in ("??", "XX"):
            byte_list.append(0x00)
            mask_list.append(0x00)
            has_wildcard = True
        else:
            try:
                byte_val = int(token_upper, 16)
                if not 0 <= byte_val <= 255:
                    raise ValueError
                byte_list.append(byte_val)
                mask_list.append(0xFF)
            except ValueError as exc:
                raise AOBParseError(
                    f"Invalid byte token {token!r} in pattern {pattern!r}"
                ) from exc

    pattern_bytes = bytes(byte_list)
    if has_wildcard:
        mask_bytes = bytes(mask_list)
        return pattern_bytes, mask_bytes
    return pattern_bytes, None


def pattern_matches(data: bytes, pattern: bytes, mask: bytes | None = None) -> bool:
    """Check if a pattern matches data at the current position.

    Args:
        data: The data to search in.
        pattern: The pattern bytes.
        mask: Optional mask (0xFF = match, 0x00 = wildcard).

    Returns:
        True if pattern matches.
    """
    if mask is None:
        return data.startswith(pattern)
    if len(data) < len(pattern):
        return False
    for i, (p, m) in enumerate(zip(pattern, mask)):
        if m == 0xFF and data[i] != p:
            return False
    return True


def _compile_regex(pattern: bytes, mask: bytes) -> re.Pattern:
    """Compile a wildcard pattern into a regex for fast searching.

    Args:
        pattern: Pattern bytes.
        mask: Mask bytes (0xFF = match, 0x00 = wildcard).

    Returns:
        Compiled regex pattern.
    """
    if pattern in _regex_cache:
        return _regex_cache[pattern]
    parts = []
    for p, m in zip(pattern, mask):
        if m == 0x00:
            parts.append(b".")
        else:
            parts.append(re.escape(bytes([p])))
    regex = re.compile(b"".join(parts))
    _regex_cache[pattern] = regex
    return regex


def find_pattern(
    data: bytes,
    pattern: bytes | str,
) -> list[int]:
    """Find all occurrences of an AOB pattern in data.

    This is the canonical scanner entry point. All pattern searching
    should go through this function.

    Args:
        data: Data to scan.
        pattern: bytes or str pattern.

    Returns:
        List of offsets where pattern is found.
    """
    pattern_bytes, mask = parse_pattern(pattern)
    results = []
    pos = 0
    pat_len = len(pattern_bytes)
    if pat_len == 0:
        return results
    if mask is None:
        while True:
            idx = data.find(pattern_bytes, pos)
            if idx == -1:
                break
            results.append(idx)
            pos = idx + 1
        return results
    regex = _compile_regex(pattern_bytes, mask)
    for m in regex.finditer(data):
        results.append(m.start())
    return results


def find_first_pattern(
    data: bytes,
    pattern: bytes | str,
) -> int | None:
    """Find the first occurrence of an AOB pattern in data.

    Returns:
        Offset of first match, or None if not found.
    """
    pattern_bytes, mask = parse_pattern(pattern)
    pat_len = len(pattern_bytes)
    if pat_len == 0:
        return None
    if mask is None:
        idx = data.find(pattern_bytes)
        return idx if idx != -1 else None
    regex = _compile_regex(pattern_bytes, mask)
    m = regex.search(data)
    return m.start() if m else None


def validate_address(
    address: int,
    module_base: int,
    module_size: int,
    allow_outside_module: bool = False,
) -> bool:
    """Validate that an address is within the expected module range.

    Args:
        address: Address to validate.
        module_base: Base address of the module.
        module_size: Size of the module in bytes.
        allow_outside_module: If True, addresses just outside are accepted.

    Returns:
        True if address is valid.
    """
    if address <= 0:
        return False
    module_end = module_base + module_size
    if allow_outside_module:
        # Allow a small margin for edge cases
        margin = 0x10000
        return (module_base - margin) <= address <= (module_end + margin)
    return module_base <= address < module_end


def log_scan_diagnostics(
    pattern_name: str,
    pattern: bytes | str,
    matches: list[int],
    module_base: int,
    module_size: int,
) -> None:
    """Log diagnostics for a scan result.

    Args:
        pattern_name: Human-readable name of the pattern.
        pattern: The pattern that was searched.
        matches: List of match offsets.
        module_base: Module base address.
        module_size: Module size.
    """
    if len(matches) == 0:
        log.debug("AOB '%s': 0 matches", pattern_name)
    elif len(matches) == 1:
        addr = module_base + matches[0]
        rva = matches[0]
        log.info(
            "AOB '%s': 1 match at %#x (RVA=%#x)",
            pattern_name, addr, rva,
        )
    else:
        addrs = [hex(module_base + m) for m in matches[:5]]
        log.warning(
            "AOB '%s': %d matches — ambiguous. First 5: %s",
            pattern_name, len(matches), ", ".join(addrs),
        )
