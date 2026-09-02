"""Launch Crimson Atlas in a dedicated local Edge application window."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from app.static_server import StaticFrontendServer


def _find_edge() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _is_elevated() -> bool:
    """Return True when Windows launched the wrapper as administrator."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _wait_until_ready(url: str, timeout: float = 5.0) -> None:
    """Wait until the loopback frontend is accepting connections."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"Local frontend did not start: {last_error}")


def _wait_for_port(port: int, process: subprocess.Popen[bytes], timeout: float = 8.0) -> None:
    """Wait for a child service to listen, failing if it exits early."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Background service exited with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Background service did not open port {port}")


def _find_window(title: str, timeout: float = 12.0) -> int | None:
    """Find a visible top-level Windows window by its exact title."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if buffer.value == title:
                matches.append(int(hwnd))
            return True

        user32.EnumWindows(visit, 0)
        if matches:
            return matches[-1]
        time.sleep(0.1)
    return None


def _keep_window_on_top(hwnd: int) -> None:
    """Mark the Atlas window topmost without stealing focus or resizing it."""
    import ctypes

    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    if not ctypes.windll.user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
    ):
        raise ctypes.WinError()


def _wait_for_atlas_close(title: str, initial_hwnd: int) -> None:
    """Track Edge window replacement and stop only after all Atlas windows close."""
    current_hwnd: int | None = initial_hwnd
    topmost_handles: set[int] = set()
    missing_since: float | None = None
    while True:
        if current_hwnd is not None:
            if current_hwnd not in topmost_handles:
                _keep_window_on_top(current_hwnd)
                topmost_handles.add(current_hwnd)
            missing_since = None
        elif missing_since is None:
            missing_since = time.monotonic()
        elif time.monotonic() - missing_since >= 2.5:
            return

        time.sleep(0.3)
        current_hwnd = _find_window(title, timeout=0.15)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if _is_elevated():
        # Edge intentionally hands elevated launches to its normal user process.
        # Relaunching through Explorer keeps the local server and app window in
        # the same integrity context and avoids an immediate connection refusal.
        subprocess.Popen(["explorer.exe", str(project_root / "Start Crimson Atlas.bat")])
        return 0

    frontend = StaticFrontendServer(project_root / "frontend" / "dist")
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    backend = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        cwd=project_root,
        creationflags=creation_flags,
    )
    _wait_for_port(7892, backend)
    frontend.start()
    _wait_until_ready("http://127.0.0.1:7891/")
    window: subprocess.Popen[bytes] | None = None
    try:
        edge = _find_edge()
        if edge:
            profile = Path(os.environ.get("LOCALAPPDATA", project_root)) / "CrimsonAtlas" / "EdgeProfile"
            profile.mkdir(parents=True, exist_ok=True)
            window = subprocess.Popen([
                str(edge),
                "--app=http://127.0.0.1:7891/",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--disable-session-crashed-bubble",
                "--disable-background-mode",
                "--window-size=1100,720",
            ])
            hwnd = _find_window("Crimson Atlas")
            if hwnd is None:
                raise RuntimeError("Crimson Atlas window did not appear")
            _wait_for_atlas_close("Crimson Atlas", hwnd)
        else:
            webbrowser.open("http://127.0.0.1:7891/")
            print("Crimson Atlas is running. Press Ctrl+C to stop it.")
            while True:
                time.sleep(1)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        frontend.stop()
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=4)
            except subprocess.TimeoutExpired:
                backend.kill()


if __name__ == "__main__":
    raise SystemExit(main())
