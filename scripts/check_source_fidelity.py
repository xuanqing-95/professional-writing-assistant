#!/usr/bin/env python3
"""Heuristic gate for source-meaning fidelity in rewritten articles."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


NUMBER_RE = re.compile(r"(?<![\w.])(?:\d+(?:\.\d+)?%?|\d{2,4}年|\d{1,2}月|\d{1,2}日)(?![\w.])")
CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")
LATIN_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-z0-9+#.-]{1,}\b")

CAUTION_MARKERS = [
    "可能",
    "大概",
    "差不多",
    "我觉得",
    "我感觉",
    "不一定",
    "未必",
    "只能算",
    "还不能",
    "不代表",
    "看起来",
    "某种程度",
]

ABSOLUTE_MARKERS = [
    "必然",
    "一定",
    "所有",
    "任何",
    "唯一",
    "本质上",
    "彻底",
    "完全证明",
    "绝对",
    "只要",
]

STOP_TOKENS = {
    "这个",
    "那个",
    "我们",
    "他们",
    "自己",
    "一个",
    "一种",
    "还是",
    "然后",
    "但是",
    "因为",
    "所以",
    "如果",
    "其实",
    "最后",
    "后来",
    "可以",
    "没有",
    "不是",
    "而是",
    "什么",
    "时候",
    "文章",
    "问题",
    "方法",
    "事情",
    "过程",
}


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\s*", "", text, flags=re.DOTALL).strip()


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def extract_numbers(text: str) -> list[str]:
    return dedupe(NUMBER_RE.findall(text))


def count_any(text: str, markers: list[str]) -> int:
    return sum(text.count(marker) for marker in markers)


def extract_key_terms(text: str, limit: int = 24) -> list[str]:
    cjk_counts: dict[str, int] = {}
    for token in CJK_TOKEN_RE.findall(text):
        if token in STOP_TOKENS:
            continue
        if len(token) < 2:
            continue
        cjk_counts[token] = cjk_counts.get(token, 0) + 1

    latin_tokens = [token for token in LATIN_TOKEN_RE.findall(text) if len(token) > 1]
    ranked_cjk = sorted(cjk_counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    candidates = [token for token, count in ranked_cjk if count >= 2]
    candidates.extend(latin_tokens)
    return dedupe(candidates)[:limit]


def missing_terms(source: str, article: str) -> list[str]:
    terms = extract_key_terms(source)
    if len(terms) < 5:
        return []
    return [term for term in terms if term not in article]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a rewrite preserves source meaning")
    parser.add_argument("source", help="Original source Markdown")
    parser.add_argument("article", help="Final publish article Markdown")
    parser.add_argument("--warn-only", action="store_true", help="Print risks without failing")
    args = parser.parse_args()

    source = strip_frontmatter(Path(args.source).read_text(encoding="utf-8"))
    article = strip_frontmatter(Path(args.article).read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []

    source_numbers = extract_numbers(source)
    article_numbers = extract_numbers(article)
    missing_numbers = [number for number in source_numbers if number not in article_numbers]
    if missing_numbers:
        errors.append("source numbers/time markers missing from article: " + ", ".join(missing_numbers))

    source_caution = count_any(source, CAUTION_MARKERS)
    article_caution = count_any(article, CAUTION_MARKERS)
    source_absolute = count_any(source, ABSOLUTE_MARKERS)
    article_absolute = count_any(article, ABSOLUTE_MARKERS)

    if source_caution >= 3 and article_caution == 0:
        errors.append("source uncertainty markers were removed; article may overstate the author's certainty")
    elif source_caution >= 3 and article_caution < source_caution // 3:
        warnings.append(
            f"source uncertainty is much lighter in article: source={source_caution}, article={article_caution}"
        )

    new_absolute = max(0, article_absolute - source_absolute)
    if new_absolute >= 3:
        errors.append(
            f"article adds many absolute markers not supported by source: source={source_absolute}, article={article_absolute}"
        )
    elif new_absolute >= 1:
        warnings.append(
            f"article adds stronger certainty markers: source={source_absolute}, article={article_absolute}"
        )

    lost_terms = missing_terms(source, article)
    if len(lost_terms) >= 10:
        errors.append("many repeated source terms disappeared: " + ", ".join(lost_terms[:12]))
    elif len(lost_terms) >= 5:
        warnings.append("some repeated source terms disappeared: " + ", ".join(lost_terms[:8]))

    for warning in warnings:
        print(f"WARN {warning}")

    if errors and not args.warn_only:
        print("FAIL source fidelity check")
        for error in errors:
            print(f"- {error}")
        return 1

    if errors:
        print("WARN source fidelity risks")
        for error in errors:
            print(f"- {error}")
    else:
        print("PASS source fidelity check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
