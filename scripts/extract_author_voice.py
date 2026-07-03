#!/usr/bin/env python3
"""Create a source-local author voice seed from a Markdown draft.

The seed is descriptive, not prescriptive. It helps the workflow extract the
current author's style without importing voice markers from examples or prior
test articles.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\s*", re.DOTALL)
CODE_RE = re.compile(r"```.*?```", re.DOTALL)
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")
ENGLISH_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")

TRANSITION_CANDIDATES = [
    "后来",
    "其实",
    "但是",
    "但",
    "不过",
    "所以",
    "因为",
    "反而",
    "没想到",
    "真正",
    "原来",
    "一开始",
    "最后",
]

STANCE_CANDIDATES = [
    "我发现",
    "我觉得",
    "我感觉",
    "我以为",
    "我意识到",
    "对我来说",
    "我的经验",
    "我当时",
    "我现在",
]

CAUTION_CANDIDATES = ["可能", "大概", "也许", "不一定", "对我来说", "我感觉", "我倾向于"]
CERTAINTY_CANDIDATES = ["一定", "必须", "显然", "本质上", "真正", "核心", "绝对"]

STOP_PHRASES = {
    "这个",
    "那个",
    "一个",
    "一些",
    "自己",
    "他们",
    "我们",
    "你们",
    "因为",
    "所以",
    "但是",
    "如果",
    "就是",
    "其实",
    "后来",
    "时候",
    "没有",
    "不是",
    "可以",
    "还是",
    "什么",
}


def clean_markdown(text: str) -> str:
    text = FRONTMATTER_RE.sub("", text)
    text = CODE_RE.sub("", text)
    text = IMAGE_RE.sub("", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    return text


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.findall(text) if s.strip()]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def count_any(text: str, candidates: list[str]) -> dict[str, int]:
    return {item: text.count(item) for item in candidates if text.count(item) > 0}


def repeated_phrases(text: str, limit: int = 12) -> list[dict[str, int | str]]:
    counter: Counter[str] = Counter()
    for match in CHINESE_RE.findall(text):
        if match in STOP_PHRASES:
            continue
        if any(stop in match for stop in ("这是", "就是", "如果", "因为", "所以")) and len(match) <= 4:
            continue
        counter[match] += 1
    for match in ENGLISH_RE.findall(text):
        counter[match] += 1
    return [
        {"phrase": phrase, "count": count}
        for phrase, count in counter.most_common(limit)
        if count >= 2
    ]


def sentence_length_bucket(avg: float) -> str:
    if avg < 18:
        return "short / spoken"
    if avg < 35:
        return "mixed"
    return "long / reflective"


def build_voice_seed(text: str) -> dict[str, object]:
    cleaned = clean_markdown(text)
    sents = sentences(cleaned)
    paras = paragraphs(cleaned)
    sentence_lengths = [len(s) for s in sents] or [0]
    paragraph_lengths = [len(p) for p in paras] or [0]
    first_person = cleaned.count("我")
    collective = cleaned.count("我们")
    question_count = len(re.findall(r"[?？]", cleaned))
    avg_sentence = round(sum(sentence_lengths) / len(sentence_lengths), 1)
    avg_paragraph = round(sum(paragraph_lengths) / len(paragraph_lengths), 1)

    return {
        "stats": {
            "characters": len(cleaned),
            "paragraphs": len(paras),
            "sentences": len(sents),
            "avg_sentence_length": avg_sentence,
            "avg_paragraph_length": avg_paragraph,
            "sentence_rhythm": sentence_length_bucket(avg_sentence),
            "first_person_count": first_person,
            "collective_count": collective,
            "question_count": question_count,
        },
        "source_derived_markers": {
            "stance": count_any(cleaned, STANCE_CANDIDATES),
            "transitions": count_any(cleaned, TRANSITION_CANDIDATES),
            "caution": count_any(cleaned, CAUTION_CANDIDATES),
            "certainty": count_any(cleaned, CERTAINTY_CANDIDATES),
        },
        "repeated_phrases": repeated_phrases(cleaned),
    }


def build_voice_seed_markdown(text: str) -> str:
    seed = build_voice_seed(text)
    stats = seed["stats"]
    markers = seed["source_derived_markers"]
    phrases = seed["repeated_phrases"]

    lines = [
        "# 00 Author Voice Seed",
        "",
        "This file is generated only from the current source draft.",
        "Use it as evidence for `04a_author_voice_profile.md`; do not treat it as a universal style template.",
        "",
        "## Quantitative Fingerprint",
        "",
    ]
    for key, value in stats.items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Source-Derived Markers", ""])
    for group, values in markers.items():
        lines.append(f"### {group}")
        if values:
            for marker, count in values.items():
                lines.append(f"- {marker}: {count}")
        else:
            lines.append("- (none detected)")
        lines.append("")

    lines.extend(["## Repeated Phrases", ""])
    if phrases:
        for item in phrases:
            lines.append(f"- {item['phrase']}: {item['count']}")
    else:
        lines.append("- (none repeated enough to count)")

    lines.extend(
        [
            "",
            "## How To Use",
            "",
            "- Preserve only markers that are meaningful in context, not every high-frequency word.",
            "- If a marker is generic, downgrade it unless it shapes the author's judgment rhythm.",
            "- Never import domain vocabulary from examples, evals, or prior users.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a source-local author voice seed")
    parser.add_argument("source", help="Markdown source draft")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()

    text = Path(args.source).read_text(encoding="utf-8")
    if args.json:
        print(json.dumps(build_voice_seed(text), ensure_ascii=False, indent=2))
    else:
        print(build_voice_seed_markdown(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
