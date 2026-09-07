"""Client for the local Crimson Route API."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib import error, request

log = logging.getLogger(__name__)


class CrimsonRouteError(RuntimeError):
    """Raised when the Crimson Route API request fails."""


class CrimsonRouteClient:
    """Small synchronous client for Crimson Route's local HTTP API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:17893",
        timeout: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        data: bytes | None = None
        headers = {
            "Accept": "application/json",
        }

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            url=url,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()

        except error.HTTPError as exc:
            raw = exc.read()

            try:
                payload = json.loads(raw.decode("utf-8"))
                message = payload.get("error") or str(payload)
            except Exception:
                message = raw.decode("utf-8", errors="replace") or str(exc)

            raise CrimsonRouteError(
                f"Crimson Route returned HTTP {exc.code}: {message}"
            ) from exc

        except error.URLError as exc:
            raise CrimsonRouteError(
                f"Crimson Route is not reachable at {self.base_url}: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise CrimsonRouteError(
                f"Crimson Route request timed out: {url}"
            ) from exc

        if not raw:
            return {}

        try:
            result = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CrimsonRouteError(
                f"Crimson Route returned invalid JSON from {path}"
            ) from exc

        if not isinstance(result, dict):
            raise CrimsonRouteError(
                f"Unexpected Crimson Route response from {path}"
            )

        return result

    # ------------------------------------------------------------------
    # Connection / state
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when the Crimson Route API is reachable."""
        try:
            state = self.get_state()
            api = state.get("api", {})
            return bool(api.get("enabled", True))
        except CrimsonRouteError:
            return False

    def get_state(self) -> dict[str, Any]:
        """Read a complete bounded state snapshot."""
        return self._request_json("GET", "/v1/state")

    def get_player(self) -> dict[str, Any]:
        """Read Crimson Route's current player position."""
        return self._request_json("GET", "/v1/player")

    def get_navigation(self) -> dict[str, Any]:
        """Read current navigation and route state."""
        return self._request_json("GET", "/v1/navigation")

    # ------------------------------------------------------------------
    # Route calculation
    # ------------------------------------------------------------------

    def request_route(
        self,
        destination_x: float,
        destination_z: float,
        *,
        destination_y: float | None = None,
        height_reliable: bool = False,
        alternatives: bool = True,
        apply_to_overlay: bool = False,
        override_manual_route: bool = False,
        start: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Queue a route calculation to a world-space destination.

        An explicit ``start`` point can be provided so Crimson Route does not
        need to sample the current player position itself.
        """
        destination: dict[str, Any] = {
            "x": float(destination_x),
            "z": float(destination_z),
            "height_reliable": bool(height_reliable),
        }

        if destination_y is not None:
            destination["y"] = float(destination_y)

        payload: dict[str, Any] = {
            "destination": destination,
            "alternatives": bool(alternatives),
            "apply_to_overlay": bool(apply_to_overlay),
            "override_manual_route": bool(override_manual_route),
        }

        if start is not None:
            payload["start"] = {
                "x": float(start.get("x", 0.0)),
                "y": float(start.get("y", 0.0)),
                "z": float(start.get("z", 0.0)),
                "height_reliable": bool(start.get("height_reliable", True)),
            }

        return self._request_json(
            "POST",
            "/v1/route-requests",
            payload,
        )

    def get_route_request(self, request_id: int) -> dict[str, Any]:
        """Read the current state/result of an asynchronous route request."""
        return self._request_json(
            "GET",
            f"/v1/route-requests/{int(request_id)}",
        )

    def wait_for_route(
        self,
        request_id: int,
        *,
        timeout: float = 20.0,
        poll_interval: float = 0.25,
    ) -> dict[str, Any]:
        """Wait until an asynchronous route request completes or fails."""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            result = self.get_route_request(request_id)
            state = result.get("state")

            if state == "completed":
                return result

            if state == "failed":
                message = result.get("error") or "route calculation failed"
                raise CrimsonRouteError(str(message))

            time.sleep(poll_interval)

        raise CrimsonRouteError(
            f"Route request {request_id} timed out after {timeout:.1f}s"
        )

    def calculate_route(
        self,
        destination_x: float,
        destination_z: float,
        *,
        destination_y: float | None = None,
        height_reliable: bool = False,
        alternatives: bool = True,
        apply_to_overlay: bool = False,
        timeout: float = 20.0,
        start: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Queue a route and wait for its completed result."""
        queued = self.request_route(
            destination_x,
            destination_z,
            destination_y=destination_y,
            height_reliable=height_reliable,
            alternatives=alternatives,
            apply_to_overlay=apply_to_overlay,
            override_manual_route=False,
            start=start,
        )

        request_id = queued.get("request_id")
        if request_id is None:
            raise CrimsonRouteError(
                "Crimson Route did not return request_id"
            )

        return self.wait_for_route(
            int(request_id),
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Display / alternatives
    # ------------------------------------------------------------------

    def select_route(
        self,
        index: int,
        candidate_set_revision: int | None = None,
    ) -> dict[str, Any]:
        """Select a primary/alternative route from the current candidate set."""
        payload: dict[str, Any] = {
            "index": int(index),
        }

        if candidate_set_revision is not None:
            payload["candidate_set_revision"] = int(candidate_set_revision)

        return self._request_json(
            "POST",
            "/v1/navigation/selected-route",
            payload,
        )

    def clear_display_route(self) -> dict[str, Any]:
        """Clear a route currently displayed by the Crimson Route API."""
        return self._request_json(
            "DELETE",
            "/v1/navigation/display-route",
        )
