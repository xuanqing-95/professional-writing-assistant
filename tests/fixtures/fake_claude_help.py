#!/usr/bin/env python3
"""Test fixture that mimics Claude Code --help output."""

from __future__ import annotations


def main() -> int:
    print("Usage: claude [options] [prompt]")
    print("  -p, --print")
    print("  --output-format <format>")
    print("  --no-session-persistence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
