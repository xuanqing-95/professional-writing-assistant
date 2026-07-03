#!/usr/bin/env python3
"""Check whether the publish body reads like an article, not a work note."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

INTERNAL_SECTIONS = [
    "Title Options",
    "Final Article",
    "Image Placement Notes",
    "Screenshot-Worthy Lines",
    "Reusable Reader Component",
    "Credibility Notes",
    "09 Final Article",
]

DOCUMENTESE_PATTERNS = [
    r"这篇文章(想|要|将|会)",
    r"本文(将|会|主要|旨在)",
    r"下面(我|我们)?(会|将|来)",
    r"以下(是|为|内容)",
    r"首先(我们)?需要",
    r"今天(想|来|和大家)",
    r"本文分为",
]

SCENE_PATTERNS = [
    r"我",
    r"我们",
    r"朋友",
    r"客户",
    r"团队",
    r"学员",
    r"老板",
    r"用户",
    r"那天",
    r"当时",
    r"上周",
    r"第一次",
    r"有一次",
]

TENSION_PATTERNS = [
    r"但",
    r"却",
    r"反而",
    r"没想到",
    r"真正",
    r"最难",
    r"卡住",
    r"问题",
    r"尴尬",
    r"反常",
    r"失败",
    r"结果",
]

METHOD_MARKERS = [
    "步骤",
    "方法",
    "清单",
    "模板",
    "公式",
    "结构是",
    "```",
]

REPETITIVE_ENDING_PATTERNS = [
    r"总之",
    r"最后.*最后",
    r"归根结底",
    r"说到底",
    r"核心.*核心",
    r"真正.*真正",
]


def strip_images(text: str) -> str:
    return IMAGE_RE.sub("", text)


def article_body(text: str) -> str:
    return strip_images(text).strip()


def first_chars(text: str, count: int) -> str:
    return article_body(text).replace("\n", "")[:count]


def last_chars(text: str, count: int) -> str:
    return article_body(text).replace("\n", "")[-count:]


def count_matches(patterns: list[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text))


def count_markdown_tables(text: str) -> int:
    return len(re.findall(r"^\|.*---.*\|?$", text, flags=re.MULTILINE))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check article readability and narrative pull")
    parser.add_argument("article", help="Path to final_publish_article.md")
    parser.add_argument("--source-image-count", type=int, default=0)
    parser.add_argument("--max-tables", type=int, default=1)
    args = parser.parse_args()

    path = Path(args.article).resolve()
    if not path.exists():
        print(f"FAIL article not found: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    for section in INTERNAL_SECTIONS:
        if section in text:
            errors.append(f"internal workflow section leaked into publish body: {section}")

    image_count = len(IMAGE_RE.findall(text))
    if args.source_image_count and image_count < args.source_image_count:
        errors.append(
            f"source has {args.source_image_count} images but publish body has {image_count}"
        )

    table_count = count_markdown_tables(text)
    if table_count > args.max_tables:
        errors.append(
            f"publish body has {table_count} markdown tables; max allowed is {args.max_tables}. Rewrite most tables as prose, short lists, or templates."
        )

    opening = first_chars(text, 700)
    if re.search("|".join(DOCUMENTESE_PATTERNS), opening):
        errors.append("opening sounds like a document setup instead of an article")

    if count_matches(SCENE_PATTERNS, opening) < 1:
        errors.append("opening lacks a concrete human scene or speaker")

    if count_matches(TENSION_PATTERNS, opening) < 1:
        errors.append("opening lacks tension, contradiction, pressure, or result")

    early = first_chars(text, 900)
    method_hits = sum(1 for marker in METHOD_MARKERS if marker in early)
    if method_hits >= 2:
        warnings.append("method/framework language appears very early; verify reader curiosity is established first")

    headings = HEADING_RE.findall(text)
    doc_heading_count = sum(
        1
        for heading in headings
        if any(marker in heading for marker in ["方法", "清单", "模板", "步骤", "逻辑", "组件"])
    )
    if doc_heading_count >= 3:
        warnings.append("many headings sound like documentation; consider more narrative section titles")

    ending = last_chars(text, 900)
    repetitive_hits = count_matches(REPETITIVE_ENDING_PATTERNS, ending)
    if repetitive_hits >= 4:
        errors.append("ending repeats the same thesis too many times; cut to one earned judgment")

    if len(re.findall(r"。", ending)) > 12:
        warnings.append("ending is long; consider cutting after the strongest final judgment")

    if errors:
        print("FAIL article readability check")
        for error in errors:
            print(f"- {error}")
        for warning in warnings:
            print(f"WARN {warning}")
        return 1

    for warning in warnings:
        print(f"WARN {warning}")
    print("PASS article readability check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
