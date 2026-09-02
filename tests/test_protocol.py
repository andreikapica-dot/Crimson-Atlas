"""WebSocket protocol tests."""

from __future__ import annotations

import json
import unittest

from app.protocol import (
    POSITION_PACKET_FIELDS,
    POSITION_TYPE,
    build_position_packet,
    validate_position_packet,
)


class TestBuildPositionPacket(unittest.TestCase):
    """Test position packet builder."""

    def test_build_returns_all_fields(self) -> None:
        packet = build_position_packet(
            x=-9668.29,
            y=659.56,
            z=220.84,
            local_x=-668.29,
            local_y=659.56,
            local_z=220.84,
            offset_x=-9000.0,
            offset_z=0.0,
            reader="physics_hook",
            timestamp=1234567890.0,
        )
        self.assertEqual(packet["type"], POSITION_TYPE)
        self.assertAlmostEqual(packet["x"], -9668.29)
        self.assertAlmostEqual(packet["y"], 659.56)
        self.assertAlmostEqual(packet["z"], 220.84)
        self.assertEqual(packet["realm"], "pywel")
        self.assertAlmostEqual(packet["localX"], -668.29)
        self.assertAlmostEqual(packet["localY"], 659.56)
        self.assertAlmostEqual(packet["localZ"], 220.84)
        self.assertAlmostEqual(packet["offsetX"], -9000.0)
        self.assertAlmostEqual(packet["offsetZ"], 0.0)
        self.assertEqual(packet["reader"], "physics_hook")
        self.assertEqual(packet["timestamp"], 1234567890.0)

    def test_build_reader_static_xyz(self) -> None:
        packet = build_position_packet(
            x=100.0,
            y=50.0,
            z=200.0,
            local_x=100.0,
            local_y=50.0,
            local_z=200.0,
            offset_x=0.0,
            offset_z=0.0,
            reader="static_xyz",
            timestamp=1234567890.0,
        )
        self.assertEqual(packet["reader"], "static_xyz")

    def test_build_detects_abyss_from_height(self) -> None:
        packet = build_position_packet(
            x=0.0, y=1500.0, z=0.0,
            local_x=0.0, local_y=1500.0, local_z=0.0,
            offset_x=0.0, offset_z=0.0,
            reader="physics_hook", timestamp=1234567890.0,
        )
        self.assertEqual(packet["realm"], "abyss")


class TestValidatePositionPacket(unittest.TestCase):
    """Test position packet validator."""

    def test_valid_packet(self) -> None:
        packet = build_position_packet(
            x=1.0,
            y=2.0,
            z=3.0,
            local_x=1.0,
            local_y=2.0,
            local_z=3.0,
            offset_x=0.0,
            offset_z=0.0,
            reader="physics_hook",
            timestamp=1234567890.0,
        )
        self.assertTrue(validate_position_packet(packet))

    def test_missing_type(self) -> None:
        packet: dict = {"x": 1.0}
        self.assertFalse(validate_position_packet(packet))

    def test_wrong_type(self) -> None:
        packet: dict = {"type": "wrong"}
        self.assertFalse(validate_position_packet(packet))

    def test_missing_field(self) -> None:
        packet: dict = {"type": POSITION_TYPE, "x": 1.0}
        self.assertFalse(validate_position_packet(packet))

    def test_non_numeric_field(self) -> None:
        packet = build_position_packet(
            x="bad",
            y=2.0,
            z=3.0,
            local_x=1.0,
            local_y=2.0,
            local_z=3.0,
            offset_x=0.0,
            offset_z=0.0,
            reader="physics_hook",
            timestamp=1234567890.0,
        )
        self.assertFalse(validate_position_packet(packet))

    def test_non_string_reader(self) -> None:
        packet = build_position_packet(
            x=1.0,
            y=2.0,
            z=3.0,
            local_x=1.0,
            local_y=2.0,
            local_z=3.0,
            offset_x=0.0,
            offset_z=0.0,
            reader=123,  # type: ignore[arg-type]
            timestamp=1234567890.0,
        )
        self.assertFalse(validate_position_packet(packet))

    def test_not_a_dict(self) -> None:
        self.assertFalse(validate_position_packet("not a dict"))  # type: ignore[arg-type]
        self.assertFalse(validate_position_packet(123))  # type: ignore[arg-type]


class TestPositionPacketRoundTrip(unittest.TestCase):
    """Test JSON serialization round trip."""

    def test_json_round_trip(self) -> None:
        packet = build_position_packet(
            x=-9668.29,
            y=659.56,
            z=220.84,
            local_x=-668.29,
            local_y=659.56,
            local_z=220.84,
            offset_x=-9000.0,
            offset_z=0.0,
            reader="physics_hook",
            timestamp=1234567890.0,
        )
        serialized = json.dumps(packet)
        parsed = json.loads(serialized)
        self.assertTrue(validate_position_packet(parsed))
        self.assertAlmostEqual(parsed["x"], -9668.29)
        self.assertAlmostEqual(parsed["offsetX"], -9000.0)


if __name__ == "__main__":
    unittest.main()
