#!/usr/bin/env python3
"""Heuristic gate for preserving source author voice in rewritten articles."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


GENERIC_OPENING_PATTERNS = [
    "这篇文章想讲",
    "本文将",
    "本文主要",
    "下面我会",
    "首先我们需要",
    "在当今",
    "随着人工智能",
]

GENERIC_PHRASES = [
    "综上所述",
    "值得注意的是",
    "毋庸置疑",
    "不可否认",
    "在这个快速变化的时代",
    "赋能",
    "抓手",
    "闭环",
    "降本增效",
]

SOURCE_DERIVED_MARKER_CANDIDATES = [
    "我发现",
    "我觉得",
    "我感觉",
    "我一开始",
    "我原来",
    "我以为",
    "对我来说",
    "后来",
    "其实",
    "这件事",
    "不是",
    "而是",
    "可能",
    "但",
    "但是",
]

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def count(text: str, needle: str) -> int:
    return text.count(needle)


def opening(text: str, limit: int = 220) -> str:
    stripped = re.sub(r"^---\n.*?\n---\s*", "", text, flags=re.DOTALL).strip()
    lines = [line.strip("# ").strip() for line in stripped.splitlines() if line.strip()]
    return "\n".join(lines[:4])[:limit]


def marker_density(text: str, markers: list[str]) -> dict[str, int]:
    return {marker: count(text, marker) for marker in markers}


def section(profile: str, name: str) -> str:
    matches = list(SECTION_RE.finditer(profile))
    for index, match in enumerate(matches):
        if match.group(1).strip().lower() != name.lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(profile)
        return profile[start:end].strip()
    return ""


def list_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            stripped = stripped[1:].strip()
        elif re.match(r"^\d+\.\s+", stripped):
            stripped = re.sub(r"^\d+\.\s+", "", stripped)
        else:
            continue
        stripped = stripped.strip("`'\"“”")
        if 2 <= len(stripped) <= 24:
            items.append(stripped)
    return items


def profile_markers(profile: str) -> list[str]:
    markers: list[str] = []
    for section_name in ("Signature Phrases / Moves", "Preserve", "Migration Rules"):
        markers.extend(list_items(section(profile, section_name)))
    return dedupe([marker for marker in markers if not marker.lower().startswith(("do not", "avoid"))])


def profile_forbidden(profile: str) -> list[str]:
    return dedupe(list_items(section(profile, "Do Not Introduce")))


def source_derived_markers(source: str) -> list[str]:
    return [marker for marker in SOURCE_DERIVED_MARKER_CANDIDATES if marker in source]


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether rewritten article preserves author voice")
    parser.add_argument("source", help="Original source Markdown")
    parser.add_argument("article", help="Final publish article Markdown")
    parser.add_argument("--profile", help="Optional completed 04a_author_voice_profile.md")
    args = parser.parse_args()

    source_path = Path(args.source)
    article_path = Path(args.article)
    source = source_path.read_text(encoding="utf-8")
    article = article_path.read_text(encoding="utf-8")
    profile = Path(args.profile).read_text(encoding="utf-8") if args.profile else ""

    errors: list[str] = []
    warnings: list[str] = []

    source_i = count(source, "我")
    article_i = count(article, "我")
    article_we = count(article, "我们")

    if source_i >= 8 and article_i < 5:
        errors.append(
            f"first-person voice likely flattened: source has {source_i} occurrences of 我, article has {article_i}"
        )
    elif source_i >= 8 and article_i < max(3, source_i // 8):
        warnings.append(
            f"first-person voice is much lighter than source: source 我={source_i}, article 我={article_i}"
        )

    if article_we > article_i * 2 and source_i >= 8:
        warnings.append(
            f"article may have shifted from personal voice to collective voice: 我={article_i}, 我们={article_we}"
        )

    article_opening = opening(article)
    for phrase in GENERIC_OPENING_PATTERNS:
        if phrase in article_opening:
            errors.append(f"generic opening phrase detected: {phrase}")

    leaked_generic = [phrase for phrase in GENERIC_PHRASES if phrase in article]
    if leaked_generic:
        warnings.append("generic platform/AI phrases detected: " + ", ".join(leaked_generic))

    markers = profile_markers(profile) if profile else source_derived_markers(source)
    forbidden = profile_forbidden(profile) if profile else []

    for phrase in forbidden:
        if phrase and phrase in article:
            errors.append(f"phrase forbidden by author voice profile detected: {phrase}")

    source_markers = marker_density(source, markers)
    article_markers = marker_density(article, markers)
    source_active = [marker for marker, value in source_markers.items() if value > 0]
    preserved = [marker for marker in source_active if article_markers.get(marker, 0) > 0]
    if len(source_active) >= 4 and len(preserved) < 2:
        errors.append(
            "source signature markers were mostly lost: "
            + ", ".join(source_active)
            + f"; preserved: {', '.join(preserved) or '(none)'}"
        )
    elif len(source_active) >= 4 and len(preserved) < 3:
        warnings.append(
            "few source signature markers preserved: "
            + f"{', '.join(preserved) or '(none)'} from {', '.join(source_active)}"
        )

    if re.search(r"^#{1,3}\s*(背景|方法|步骤|总结|结论)\s*$", article, re.MULTILINE):
        warnings.append("document-like section heading detected; verify it still sounds like the author")

    for warning in warnings:
        print(f"WARN {warning}")

    if errors:
        print("FAIL author voice check")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS author voice check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
