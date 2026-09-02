"""Frozen Crimson Atlas backend entry point."""

from __future__ import annotations

import sys

from app.main import main, self_test


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
