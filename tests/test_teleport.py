"""Teleport command and capture-buffer tests."""

from __future__ import annotations

import math
import struct
import unittest
from unittest.mock import MagicMock

from memory.process import GameProcess
from memory.teleport import TeleportEngine


class TestTeleportEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.process = MagicMock(spec=GameProcess)
        self.engine = TeleportEngine(self.process)

    def test_unavailable_until_physics_hook_is_connected(self) -> None:
        self.assertFalse(self.engine.available)
        self.assertEqual(self.engine.teleport_to(1, 2, 3), (False, "Teleport hook not installed"))

    def test_absolute_coordinates_are_converted_to_local(self) -> None:
        self.engine.set_physics_hook(0x1000)
        ok, error = self.engine.teleport_to(110, 220, 330, (10, 20, 30))
        self.assertTrue(ok, error)
        self.assertTrue(self.engine.available)
        address, payload = self.process.write_bytes.call_args.args
        self.assertEqual(address, 0x1010)
        self.assertEqual(struct.unpack("<ffffI", payload), (100.0, 220.0, 300.0, 0.0, 1))

    def test_non_finite_coordinates_are_rejected_without_writing(self) -> None:
        self.engine.set_physics_hook(0x2000)
        ok, error = self.engine.teleport_to(math.nan, 2, 3)
        self.assertFalse(ok)
        self.assertIn("finite", error)
        self.process.write_bytes.assert_not_called()

    def test_tuple_coordinate_is_rejected_before_struct_pack(self) -> None:
        self.engine.set_physics_hook(0x2000)
        ok, error = self.engine.teleport_to((1, 2), 2, 3)  # type: ignore[arg-type]
        self.assertFalse(ok)
        self.assertIn("real numbers", error)
        self.process.write_bytes.assert_not_called()

    def test_clear_hook_disables_future_writes(self) -> None:
        self.engine.set_physics_hook(0x2000)
        self.engine.clear_physics_hook()
        self.assertFalse(self.engine.available)


if __name__ == "__main__":
    unittest.main()
