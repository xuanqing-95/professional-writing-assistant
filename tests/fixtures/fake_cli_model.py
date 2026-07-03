#!/usr/bin/env python3
"""Test fixture that mimics a CLI model reading a prompt from stdin."""

from __future__ import annotations

import os
import sys


def main() -> int:
    _prompt = sys.stdin.read()
    role = os.environ.get("PWA_ROLE", "unknown")
    print(f"# {role}\n\nfilled\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
