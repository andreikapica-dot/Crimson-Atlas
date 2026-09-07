"""Regression tests for Windows console encoding/locale handling.

On legacy Windows locales (e.g. Korean CP949), the default stdout/stderr
encoding cannot represent characters like em-dash (U+2014). These tests
verify that ``configure_console_encoding`` safely switches the streams to
UTF-8 with ``errors="replace"`` so startup prints never crash.
"""

from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import patch

from logging_config import configure_console_encoding


class _FakeStream:
    """Minimal stream simulating a legacy Windows console encoding."""

    def __init__(self, encoding="cp949", error_on_unicode=False):
        self._encoding = encoding
        self._error_on_unicode = error_on_unicode
        self.written: list[str] = []

    def getvalue(self) -> str:
        return "".join(self.written)

    @property
    def encoding(self) -> str:
        return self._encoding

    def write(self, text: str) -> int:
        if self._error_on_unicode:
            text.encode(self._encoding, errors="strict")
        self.written.append(text)
        return len(text)

    def flush(self) -> None:
        pass

    def reconfigure(self, *args, **kwargs) -> None:
        new_encoding = kwargs.get("encoding", self._encoding)
        self._encoding = new_encoding
        self._error_on_unicode = False


class TestConsoleEncoding(unittest.TestCase):
    """Test console encoding configuration."""

    def test_configure_utf8_replaces_em_dash_safely(self) -> None:
        """Em-dash must be writable on a simulated CP949 stream after configuration."""
        fake = _FakeStream(encoding="cp949", error_on_unicode=True)
        with patch.object(sys, "stdout", fake), patch.object(sys, "stderr", fake):
            configure_console_encoding()
            fake.write("\u2014")
        self.assertIn("\u2014", fake.getvalue())
        self.assertEqual(fake.encoding, "utf-8")

    def test_configure_does_not_raise_on_none_stream(self) -> None:
        """configure_console_encoding must tolerate sys.stdout/sys.stderr being None."""
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
            configure_console_encoding()

    def test_configure_handles_missing_reconfigure(self) -> None:
        """Streams without reconfigure (e.g. some C-level handles) must not crash."""

        class _NoReconfigure:
            @property
            def encoding(self):
                return "cp949"

        with patch.object(sys, "stdout", _NoReconfigure()), patch.object(sys, "stderr", _NoReconfigure()):
            configure_console_encoding()

    def test_configure_handles_reconfigure_error(self) -> None:
        """If reconfigure raises, configure_console_encoding must swallow it."""

        class _BadReconfigure:
            @property
            def encoding(self):
                return "cp949"

            def reconfigure(self, *args, **kwargs):
                raise ValueError("cannot reconfigure")

        with patch.object(sys, "stdout", _BadReconfigure()), patch.object(sys, "stderr", _BadReconfigure()):
            configure_console_encoding()

    def test_print_header_survives_cp949_after_configure(self) -> None:
        """print_header with em-dash must not raise on a CP949 stream after configure."""
        from app.main import print_header

        fake = _FakeStream(encoding="cp949", error_on_unicode=True)
        with patch.object(sys, "stdout", fake):
            configure_console_encoding()
            print_header()

        self.assertIn("\u2014", fake.getvalue())


if __name__ == "__main__":
    unittest.main()
