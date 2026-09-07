"""Crimson Route Local API client tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from services.crimson_route import CrimsonRouteClient


class TestCrimsonRouteClient(unittest.TestCase):
    """Verify requests sent to the optional Crimson Route integration."""

    def test_route_can_be_applied_to_in_game_overlay(self) -> None:
        client = CrimsonRouteClient()
        client._request_json = Mock(return_value={"request_id": 42})  # type: ignore[method-assign]

        result = client.request_route(
            -10396.25,
            -4640.75,
            alternatives=False,
            apply_to_overlay=True,
        )

        self.assertEqual(result, {"request_id": 42})
        client._request_json.assert_called_once_with(
            "POST",
            "/v1/route-requests",
            {
                "destination": {
                    "x": -10396.25,
                    "z": -4640.75,
                    "height_reliable": False,
                },
                "alternatives": False,
                "apply_to_overlay": True,
                "override_manual_route": False,
            },
        )

    def test_clear_display_route_uses_navigation_endpoint(self) -> None:
        client = CrimsonRouteClient()
        client._request_json = Mock(return_value={"ok": True})  # type: ignore[method-assign]

        result = client.clear_display_route()

        self.assertEqual(result, {"ok": True})
        client._request_json.assert_called_once_with(
            "DELETE",
            "/v1/navigation/display-route",
        )


if __name__ == "__main__":
    unittest.main()
