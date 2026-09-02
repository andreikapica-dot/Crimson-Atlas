"""AOB pattern tests."""

from __future__ import annotations

import struct
import unittest

from memory.aob import (
    AOBParseError,
    find_first_pattern,
    find_pattern,
    normalize_pattern,
    parse_pattern,
    pattern_matches,
    validate_address,
    log_scan_diagnostics,
)
from memory.scanner import AOBScanner
from memory.types import SignatureSet
from memory.signatures import get_signatures


class TestNormalizePattern(unittest.TestCase):
    """Test pattern normalization."""

    def test_bytes_passthrough(self) -> None:
        """Bytes input is returned as-is."""
        raw = b"\x0F\x28\xC6"
        self.assertEqual(normalize_pattern(raw), raw)

    def test_hex_string_no_spaces(self) -> None:
        """Hex string without spaces is parsed."""
        self.assertEqual(normalize_pattern("0F28C6"), b"\x0F\x28\xC6")

    def test_hex_string_with_spaces(self) -> None:
        """Hex string with spaces is parsed."""
        self.assertEqual(normalize_pattern("0F 28 C6"), b"\x0F\x28\xC6")

    def test_mixed_case(self) -> None:
        """Case is ignored."""
        self.assertEqual(normalize_pattern("0f28c6"), b"\x0F\x28\xC6")

    def test_invalid_length(self) -> None:
        """Odd-length hex string raises."""
        with self.assertRaises(AOBParseError):
            normalize_pattern("0F28C")

    def test_invalid_hex(self) -> None:
        """Non-hex characters raise."""
        with self.assertRaises(AOBParseError):
            normalize_pattern("ZZ ZZ")

    def test_wrong_type(self) -> None:
        """Non-bytes/str input raises."""
        with self.assertRaises(AOBParseError):
            normalize_pattern(12345)  # type: ignore


class TestParsePattern(unittest.TestCase):
    """Test pattern parsing with wildcards."""

    def test_plain_bytes(self) -> None:
        """Plain bytes have no mask."""
        pattern, mask = parse_pattern(b"\x0F\x28\xC6")
        self.assertEqual(pattern, b"\x0F\x28\xC6")
        self.assertIsNone(mask)

    def test_wildcard_bytes(self) -> None:
        """0x00 in bytes is treated as wildcard."""
        pattern, mask = parse_pattern(b"\x0F\x00\xC6")
        self.assertEqual(pattern, b"\x0F\x00\xC6")
        self.assertEqual(mask, b"\xFF\x00\xFF")

    def test_wildcard_string_question_mark(self) -> None:
        """?? in string is a wildcard."""
        pattern, mask = parse_pattern("0F ?? C6")
        self.assertEqual(pattern, b"\x0F\x00\xC6")
        self.assertEqual(mask, b"\xFF\x00\xFF")

    def test_wildcard_string_xx(self) -> None:
        """XX in string is a wildcard."""
        pattern, mask = parse_pattern("0F XX C6")
        self.assertEqual(pattern, b"\x0F\x00\xC6")
        self.assertEqual(mask, b"\xFF\x00\xFF")

    def test_multiple_wildcards(self) -> None:
        """Multiple wildcards work."""
        pattern, mask = parse_pattern("?? ?? ??")
        self.assertEqual(pattern, b"\x00\x00\x00")
        self.assertEqual(mask, b"\x00\x00\x00")


class TestPatternMatches(unittest.TestCase):
    """Test pattern matching."""

    def test_exact_match(self) -> None:
        """Exact match returns True."""
        data = b"\x0F\x28\xC6\xF3"
        self.assertTrue(pattern_matches(data, b"\x0F\x28\xC6"))

    def test_no_match(self) -> None:
        """Non-match returns False."""
        data = b"\x0F\x28\xC6\xF3"
        self.assertFalse(pattern_matches(data, b"\x0F\x28\xFF"))

    def test_wildcard_match(self) -> None:
        """Wildcard matches any byte."""
        data = b"\x0F\xAB\xC6\xF3"
        self.assertTrue(pattern_matches(data, b"\x0F\x00\xC6", b"\xFF\x00\xFF"))

    def test_short_data(self) -> None:
        """Pattern longer than data returns False."""
        data = b"\x0F\x28"
        self.assertFalse(pattern_matches(data, b"\x0F\x28\xC6"))


class TestFindPattern(unittest.TestCase):
    """Test AOB finding."""

    def test_single_match(self) -> None:
        """Single match is found."""
        data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F"
        self.assertEqual(find_pattern(data, "05 06 07"), [5])

    def test_multiple_matches(self) -> None:
        """Multiple matches are found."""
        data = b"\x05\x06\x07\x00\x05\x06\x07\x00\x05\x06\x07"
        self.assertEqual(find_pattern(data, "05 06 07"), [0, 4, 8])

    def test_no_matches(self) -> None:
        """No matches returns empty list."""
        data = b"\x00\x01\x02\x03"
        self.assertEqual(find_pattern(data, "FF FF"), [])

    def test_bytes_input(self) -> None:
        """Bytes input works."""
        data = b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8"
        self.assertEqual(find_pattern(data, b"\x0F\x28\xC6"), [0])

    def test_wildcard_pattern(self) -> None:
        """Wildcard pattern matches."""
        data = b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8"
        results = find_pattern(data, "0F 28 ??")
        self.assertEqual(results, [0])

    def test_empty_pattern(self) -> None:
        """Empty pattern returns empty list."""
        data = b"\x00\x01\x02"
        self.assertEqual(find_pattern(data, ""), [])

    def test_malformed_string_raises(self) -> None:
        """Malformed hex string raises AOBParseError."""
        data = b"\x00\x01\x02"
        with self.assertRaises(AOBParseError):
            find_pattern(data, "0G 28 C6")  # invalid hex


class TestFindFirstPattern(unittest.TestCase):
    """Test first-match finding."""

    def test_found(self) -> None:
        """First match is returned."""
        data = b"\x00\x01\x02\x03\x02\x03"
        self.assertEqual(find_first_pattern(data, "02 03"), 2)

    def test_not_found(self) -> None:
        """None is returned when not found."""
        data = b"\x00\x01\x02\x03"
        self.assertIsNone(find_first_pattern(data, "FF FF"))

    def test_bytes_input(self) -> None:
        """Bytes input works."""
        data = b"\x0F\x28\xC6"
        self.assertEqual(find_first_pattern(data, b"\x0F\x28\xC6"), 0)


class TestValidateAddress(unittest.TestCase):
    """Test address validation."""

    def test_valid_inside_module(self) -> None:
        """Address inside module is valid."""
        self.assertTrue(validate_address(0x1000, 0x1000, 0x100000))

    def test_invalid_before_module(self) -> None:
        """Address before module is invalid."""
        self.assertFalse(validate_address(0x0FFF, 0x1000, 0x100000))

    def test_invalid_after_module(self) -> None:
        """Address after module is invalid."""
        self.assertFalse(validate_address(0x101000, 0x1000, 0x100000))

    def test_negative_invalid(self) -> None:
        """Negative address is invalid."""
        self.assertFalse(validate_address(-1, 0x1000, 0x100000))

    def test_zero_invalid(self) -> None:
        """Zero address is invalid."""
        self.assertFalse(validate_address(0, 0x1000, 0x100000))

    def test_outside_with_margin(self) -> None:
        """Just outside module is accepted with margin."""
        self.assertTrue(validate_address(0x0F00, 0x1000, 0x100000, allow_outside_module=True))


class TestSignatureSelection(unittest.TestCase):
    """Test signature selection."""

    def test_known_version(self) -> None:
        """Known version returns signatures."""
        sigs = get_signatures("2.00.00")
        self.assertIsInstance(sigs, SignatureSet)
        self.assertTrue(len(sigs.physics_delta) > 0)

    def test_unknown_version(self) -> None:
        """Unknown version returns empty signatures."""
        sigs = get_signatures("9.99.99")
        self.assertIsInstance(sigs, SignatureSet)
        self.assertEqual(len(sigs.physics_delta), 0)


if __name__ == "__main__":
    unittest.main()
