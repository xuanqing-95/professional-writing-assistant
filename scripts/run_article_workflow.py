#!/usr/bin/env python3
"""Create a required workflow packet for article rewriting tasks.

This script does not replace the model's writing judgment. It makes the
workflow auditable by creating fixed intermediate artifacts that must be filled
before a final article is delivered.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from extract_author_voice import build_voice_seed_markdown


REQUIRED_FILES = [
    "00_source.md",
    "00_manifest.json",
    "00_author_voice_seed.md",
    "00_media_manifest.md",
    "00_source_claim_map.md",
    "agent_tasks/strategist.md",
    "agent_tasks/interviewer.md",
    "agent_tasks/author_voice_analyst.md",
    "agent_tasks/structure_editor.md",
    "agent_tasks/narrative_editor.md",
    "agent_tasks/fidelity_reviewer.md",
    "agent_tasks/value_evaluator.md",
    "agent_tasks/spread_evaluator.md",
    "agent_tasks/credibility_risk.md",
    "agent_outputs/strategist.md",
    "agent_outputs/interviewer.md",
    "agent_outputs/author_voice_analyst.md",
    "agent_outputs/structure_editor.md",
    "agent_outputs/narrative_editor.md",
    "agent_outputs/fidelity_reviewer.md",
    "agent_outputs/value_evaluator.md",
    "agent_outputs/spread_evaluator.md",
    "agent_outputs/credibility_risk.md",
    "01_intake_diagnosis.md",
    "02_strategy_brief.md",
    "03_interview_gaps.md",
    "04a_author_voice_profile.md",
    "04_structure_review.md",
    "04b_narrative_review.md",
    "05_value_review.md",
    "06_spread_review.md",
    "07_credibility_review.md",
    "07b_source_fidelity_review.md",
    "08_rewrite_plan.md",
    "09_final_article.md",
    "final_publish_article.md",
    "10_workflow_checklist.md",
]


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def count_images(text: str) -> int:
    return len(IMAGE_RE.findall(text))


def count_headings(text: str) -> int:
    return len(re.findall(r"^#{1,6}\s+", text, re.MULTILINE))


def extract_title(text: str) -> str:
    frontmatter_title = re.search(r'^title:\s*"?(.+?)"?\s*$', text, re.MULTILINE)
    if frontmatter_title:
        return frontmatter_title.group(1).strip("* ")
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:80] or "Untitled"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def required_block(label: str) -> str:
    return f"<!-- REQUIRED: fill {label} before final answer -->"


def nearby_text(lines: list[str], image_line_index: int, direction: int) -> str:
    idx = image_line_index + direction
    while 0 <= idx < len(lines):
        candidate = lines[idx].strip()
        if (
            candidate
            and candidate != "<empty-block/>"
            and not candidate.startswith("![](")
            and not IMAGE_RE.search(candidate)
        ):
            return candidate
        idx += direction
    return ""


def extract_images(text: str) -> list[dict[str, str | int]]:
    images: list[dict[str, str | int]] = []
    lines = text.splitlines()
    for line_index, line in enumerate(lines):
        for match in IMAGE_RE.finditer(line):
            alt = match.group(1).strip()
            url = match.group(2).strip()
            before = nearby_text(lines, line_index, -1)
            after = nearby_text(lines, line_index, 1)
            caption = alt or before or after or f"Image {len(images) + 1}"
            images.append(
                {
                    "index": len(images) + 1,
                    "alt": alt,
                    "url": url,
                    "caption": caption,
                    "before": before,
                    "after": after,
                }
            )
    return images


def build_media_manifest(images: list[dict[str, str | int]]) -> str:
    if not images:
        return """# 00 Media Manifest

No source images detected.
"""

    sections = [
        "# 00 Media Manifest",
        "",
        "Use this file to preserve images and visible captions from the source draft.",
        "When rewriting, move each image to the section where it best supports the argument.",
        "Do not drop images unless the reason is recorded here.",
        "",
    ]
    for image in images:
        idx = image["index"]
        sections.extend(
            [
                f"## Image {idx}",
                "",
                f"- Source caption/alt: {image['caption']}",
                f"- Text before image: {image['before'] or '(none)'}",
                f"- Text after image: {image['after'] or '(none)'}",
                f"- Markdown: ![{image['caption']}]({image['url']})",
                f"- Final placement: {required_block(f'image {idx} final placement')}",
                f"- Keep / remove: {required_block(f'image {idx} keep or remove decision')}",
                "",
            ]
        )
    return "\n".join(sections)


def build_source_claim_map() -> str:
    return f"""# 00 Source Claim Map

Use this file to lock the source meaning before rewriting. The article may be reorganized,
but these source meanings must not be changed without explicit author verification.

## Non-Negotiable Facts
1. {required_block("fact 1 from source, with paragraph or quote evidence")}
2. {required_block("fact 2 from source, with paragraph or quote evidence")}
3. {required_block("fact 3 from source, with paragraph or quote evidence")}

## Core Claims
1. {required_block("claim 1 the source actually makes")}
2. {required_block("claim 2 the source actually makes")}
3. {required_block("claim 3 the source actually makes")}

## Causal Logic
- Because: {required_block("what the source says caused the change or result")}
- Therefore: {required_block("what conclusion the source draws")}
- Not because: {required_block("causes the rewrite must not imply")}

## Experience Boundaries
- Works when: {required_block("conditions stated or clearly implied by source")}
- Does not prove: {required_block("claims the source does not support")}
- Needs author verification: {required_block("uncertain or missing details")}

## Allowed Changes
- Structure: {required_block("what may be moved or merged")}
- Language: {required_block("what may be polished")}
- Additions: {required_block("what may be added only as labeled assumptions or editor framing")}

## Forbidden Changes
1. {required_block("meaning change to avoid")}
2. {required_block("meaning change to avoid")}
3. {required_block("meaning change to avoid")}
"""


def build_packet(source: Path, out_dir: Path, mode: str, platform: str) -> None:
    text = source.read_text(encoding="utf-8")
    title = extract_title(text)
    images = extract_images(text)
    stats = {
        "title": title,
        "source_path": str(source),
        "mode": mode,
        "platform": platform,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "wordish_count": len(re.findall(r"[\w\u4e00-\u9fff]+", text)),
        "heading_count": count_headings(text),
        "image_count": len(images),
        "required_files": REQUIRED_FILES,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write(out_dir / "00_source.md", text)
    write(out_dir / "00_manifest.json", json.dumps(stats, ensure_ascii=False, indent=2))
    write(out_dir / "00_author_voice_seed.md", build_voice_seed_markdown(text))
    write(out_dir / "00_media_manifest.md", build_media_manifest(images))
    write(out_dir / "00_source_claim_map.md", build_source_claim_map())

    agent_specs = {
        "strategist": {
            "file": "agents/strategist.md",
            "ask": "Define target reader, reader pain, article promise, core thesis, best angle, recommended structure, and what to avoid.",
            "output": "Strategy Brief",
        },
        "interviewer": {
            "file": "agents/interviewer.md",
            "ask": "Find missing scenes, evidence, constraints, before/after details, and at most three author questions.",
            "output": "Missing Material",
        },
        "author_voice_analyst": {
            "file": "agents/author_voice_analyst.md",
            "ask": "Extract the author's voice DNA from the source draft. Separate what to preserve, what to clean up, and what not to introduce. Provide migration rules that keep the rewritten article recognizably written by the same person.",
            "output": "Author Voice Profile",
        },
        "structure_editor": {
            "file": "agents/structure_editor.md",
            "ask": "Review flow, opening, section order, repetition, transitions, and ending.",
            "output": "Structure Review",
        },
        "narrative_editor": {
            "file": "agents/narrative_editor.md",
            "ask": "Remove document-like writing. Strengthen reader curiosity, opening tension, narrative arc, section progression, and ending.",
            "output": "Narrative Review",
        },
        "fidelity_reviewer": {
            "file": "agents/fidelity_reviewer.md",
            "ask": "Protect source meaning. Build or audit the source claim map, then compare the rewrite plan against the source draft. Flag facts, causality, author stance, boundaries, or claims that may be changed too much.",
            "output": "Source Fidelity Review",
        },
        "value_evaluator": {
            "file": "agents/value_evaluator.md",
            "ask": "Evaluate save-worthiness and propose reusable reader value components.",
            "output": "Reader Value Review",
        },
        "spread_evaluator": {
            "file": "agents/spread_evaluator.md",
            "ask": "Evaluate shareability, title directions, screenshot-worthy lines, and share copy.",
            "output": "Spread Review",
        },
        "credibility_risk": {
            "file": "agents/credibility_risk.md",
            "ask": "Flag unsupported claims, overgeneralization, missing boundaries, sensitive details, and safer wording.",
            "output": "Credibility Review",
        },
    }

    for agent_name, spec in agent_specs.items():
        write(
            out_dir / "agent_tasks" / f"{agent_name}.md",
            f"""
# Agent Task: {agent_name}

## Role File

Read `{spec["file"]}` before producing output.

## Source Draft

Use `../00_source.md` as the only source draft. Do not invent facts.

## Source Claim Map

Use `../00_source_claim_map.md` to protect facts, claims, causal logic, and boundaries.
Do not recommend meaning changes unless they are explicitly marked as author-verification items.

## Author Voice Seed

Use `../00_author_voice_seed.md` as source-local evidence. Do not import voice markers from examples, eval prompts, or prior users.

## Source Images

Use `../00_media_manifest.md` to preserve source images, captions, and placement intent.
If you recommend removing an image, give a concrete reason.

## Task

{spec["ask"]}

## Required Output

Return a complete `{spec["output"]}`. Include concrete recommendations grounded in the source draft.

## Provenance Requirement

The final output must be written into `agent_outputs/{agent_name}.md` and include:

```yaml
agent: {agent_name}
mode: subagent
```

If no subagent runtime is available, the main agent may fill the file only with:

```yaml
agent: {agent_name}
mode: simulated
```

Do not label simulated work as subagent work.
Subagent mode must later be recorded with a runtime-provided UUID-like agent id and raw runtime event JSON. The runner generates the matching proof JSON.
""",
        )
        write(
            out_dir / "agent_outputs" / f"{agent_name}.md",
            f"""
---
agent: {agent_name}
mode: {required_block("subagent or simulated")}
---

# {spec["output"]}

{required_block(spec["output"])}
""",
        )

    write(
        out_dir / "01_intake_diagnosis.md",
        f"""
# 01 Intake Diagnosis

- Mode: {mode}
- Platform: {platform}
- Source title: {title}
- Source stats: {stats["wordish_count"]} wordish tokens, {stats["heading_count"]} headings, {stats["image_count"]} images

## Current Topic
{required_block("current topic")}

## Target Reader
{required_block("target reader and pain")}

## Strongest Experience Asset
{required_block("specific scene/result/evidence")}

## Weakest Part
{required_block("main draft weakness")}

## Recommended Structure
{required_block("structure pattern")}

## Missing Material
{required_block("must add / nice to add / assumptions")}
""",
    )

    write(
        out_dir / "02_strategy_brief.md",
        f"""
# 02 Strategy Brief

## Target Reader
{required_block("target reader")}

## Reader Pain
{required_block("reader pain")}

## Article Promise
这篇文章帮助 [目标读者] 通过 [作者经验] 理解/掌握/避免 [核心问题]。

## Core Thesis
{required_block("core thesis")}

## Best Angle
{required_block("best angle")}

## Recommended Structure
{required_block("recommended structure")}

## What To Avoid
{required_block("what to avoid")}
""",
    )

    write(
        out_dir / "03_interview_gaps.md",
        f"""
# 03 Interview Gaps

## Must Add
1. {required_block("must add 1")}
2. {required_block("must add 2")}
3. {required_block("must add 3")}

## Nice To Add
1. {required_block("nice to add 1")}
2. {required_block("nice to add 2")}

## Questions For Author
1. {required_block("question 1")}
2. {required_block("question 2")}
3. {required_block("question 3")}

## Assumptions If Not Asking
{required_block("labeled assumptions")}
""",
    )

    write(
        out_dir / "04a_author_voice_profile.md",
        f"""
# 04a Author Voice Profile

Use `00_author_voice_seed.md`, `references/author_voice_dna.md`, and `agent_outputs/author_voice_analyst.md`.
The current source is the only authority for this author's voice.

## Voice Fingerprint
{required_block("author-specific voice fingerprint")}

## Thinking Lens
{required_block("how the author usually understands the experience")}

## Sentence Rhythm
{required_block("sentence and paragraph rhythm to preserve")}

## Signature Phrases / Moves
{required_block("recurring phrases, transitions, or judgment patterns")}

## Preserve
{required_block("voice traits and original texture to preserve")}

## Clean Up
{required_block("roughness to clean without flattening the voice")}

## Do Not Introduce
{required_block("generic or alien tone/phrases not found in source")}

## Migration Rules
{required_block("rules the rewrite must obey to remain recognizably the same author")}

## Voice Check
{required_block("how final_publish_article.md will be checked against this profile")}
""",
    )

    write(
        out_dir / "04_structure_review.md",
        f"""
# 04 Structure Review

## Current Structure Problem
{required_block("current structure problem")}

## Recommended Section Order
{required_block("recommended section order")}

## Sections To Merge Or Delete
{required_block("merge/delete suggestions")}

## Opening Improvement
{required_block("opening improvement")}

## Ending Improvement
{required_block("ending improvement")}
""",
    )

    write(
        out_dir / "04b_narrative_review.md",
        f"""
# 04b Narrative Review

## Reader Curiosity Gap
{required_block("why a real reader should continue after the opening")}

## Best Opening Material
{required_block("scene/result/contradiction/mistake/question")}

## Opening Rewrite
{required_block("opening rewrite")}

## Sections That Feel Like Documentation
{required_block("sections to rewrite or merge")}

## Repetition To Cut
{required_block("repetition to cut")}

## Ending Rewrite
{required_block("ending rewrite")}

## Final Article Arc
{required_block("scene -> false belief -> pressure -> turn -> method -> boundary -> final judgment")}
""",
    )

    write(
        out_dir / "05_value_review.md",
        f"""
# 05 Reader Value Review

## Save-Worthiness Score
{required_block("score /10")}

## Most Useful Part
{required_block("most useful part")}

## Weakest Part
{required_block("weakest part")}

## Missing Reusable Component
{required_block("missing reusable component")}

## Suggested Table / Checklist / Template
{required_block("component content")}
""",
    )

    write(
        out_dir / "06_spread_review.md",
        f"""
# 06 Spread Review

## Shareability Score
{required_block("score /10")}

## Strongest Share Reason
{required_block("strongest share reason")}

## Weakest Share Reason
{required_block("weakest share reason")}

## Better Title Directions
{required_block("title directions")}

## Screenshot-Worthy Lines
{required_block("screenshot-worthy lines")}

## Suggested Share Copy
{required_block("share copy")}
""",
    )

    write(
        out_dir / "07_credibility_review.md",
        f"""
# 07 Credibility Review

## Unsupported Claims
{required_block("unsupported claims")}

## Overgeneralized Statements
{required_block("overgeneralized statements")}

## Missing Boundaries
{required_block("missing boundaries")}

## Confidential Or Sensitive Details
{required_block("confidential/sensitive details")}

## Suggested Safer Wording
{required_block("safer wording")}
""",
    )

    write(
        out_dir / "07b_source_fidelity_review.md",
        f"""
# 07b Source Fidelity Review

Use `00_source.md`, `00_source_claim_map.md`, `08_rewrite_plan.md`, and `agent_outputs/fidelity_reviewer.md`.
This review protects the original meaning. A more polished article is not acceptable if it changes what the source meant.

## Meaning Preservation Verdict
{required_block("pass / needs revision / blocked")}

## Changed Meaning Risks
1. {required_block("risk 1: source meaning vs rewrite meaning")}
2. {required_block("risk 2: source meaning vs rewrite meaning")}
3. {required_block("risk 3: source meaning vs rewrite meaning")}

## Facts That Must Stay Exact
{required_block("facts, numbers, sequence, roles, screenshots, or constraints that must not be altered")}

## Claims That Must Be Softened
{required_block("claims that the rewrite must not overstate")}

## Additions Requiring Author Verification
{required_block("new interpretations, examples, or connective tissue that are not directly in source")}

## Required Fixes Before Final
{required_block("specific edits needed to restore source meaning")}
""",
    )

    write(
        out_dir / "08_rewrite_plan.md",
        f"""
# 08 Rewrite Plan

## Rewrite Goal
{required_block("rewrite goal")}

## Core Thesis Rewrite
- Original thesis: {required_block("original thesis")}
- New thesis: {required_block("new thesis")}

## Structure Changes
| Original structure | Problem | New structure |
|---|---|---|
| {required_block("original")} | {required_block("problem")} | {required_block("new")} |

## Material To Add
{required_block("material to add")}

## Image Placement Plan
{required_block("where each source image should appear in the rewritten article")}

## Author Voice Migration Plan
{required_block("how to preserve the author's original writing flavor while improving structure")}

## Source Meaning Preservation Plan
{required_block("what meanings must remain unchanged, what additions need author verification, and what will be deliberately softened")}

## Content To Delete Or Weaken
{required_block("content to delete/weaken")}

## Reusable Component Design
- Checklist: {required_block("checklist")}
- Process: {required_block("process")}
- Template: {required_block("template")}
- Decision Rule: {required_block("decision rule")}
- Table: {required_block("optional table only if comparison truly needs it; otherwise write 'not needed'")}

## Title Directions
{required_block("title directions")}

## Rewrite Priorities
1. {required_block("priority 1")}
2. {required_block("priority 2")}
3. {required_block("priority 3")}
""",
    )

    write(
        out_dir / "09_final_article.md",
        f"""
# 09 Final Article

## Title Options
1. {required_block("title option 1")}
2. {required_block("title option 2")}
3. {required_block("title option 3")}

## Final Article
{required_block("final article")}

## Image Placement Notes
{required_block("which source images were kept, moved, or removed")}

## Screenshot-Worthy Lines
1. {required_block("line 1")}
2. {required_block("line 2")}
3. {required_block("line 3")}

## Reusable Reader Component
{required_block("checklist/process/template/decision rule; avoid tables unless truly necessary")}

## Credibility Notes
{required_block("claims softened or marked")}
""",
    )

    write(
        out_dir / "final_publish_article.md",
        f"""
# {title}

{required_block("publish-ready article body only")}
""",
    )

    write(
        out_dir / "10_workflow_checklist.md",
        f"""
# 10 Workflow Checklist

- [ ] Read SKILL.md.
- [ ] Read relevant references.
- [ ] Read 00_media_manifest.md and preserve source images/captions when present.
- [ ] Read 00_author_voice_seed.md before filling 04a author voice profile.
- [ ] Read all role files in agents/.
- [ ] Create or use agent_tasks/*.md.
- [ ] Fill agent_outputs/*.md with `mode: subagent` or `mode: simulated`.
- [ ] Record every agent output with `scripts/run_workflow.py record-agent`; subagent records require `--runtime-event`.
- [ ] Complete 01 intake diagnosis.
- [ ] Complete 02 strategy brief.
- [ ] Complete 03 interview gaps.
- [ ] Complete 04a author voice profile.
- [ ] Complete 04 structure review.
- [ ] Complete 04b narrative review.
- [ ] Complete 05 value review.
- [ ] Complete 06 spread review.
- [ ] Complete 07 credibility review.
- [ ] Complete 07b source fidelity review.
- [ ] Complete 08 rewrite plan.
- [ ] Complete 09 final article.
- [ ] Complete final_publish_article.md with publish-ready body only.
- [ ] Verify final_publish_article.md includes all kept source images in correct positions.
- [ ] Verify final_publish_article.md does not include internal workflow notes.
- [ ] Run scripts/check_author_voice.py on 00_source.md and final_publish_article.md, with 04a_author_voice_profile.md when completed.
- [ ] Run scripts/check_article_readability.py on final_publish_article.md.
- [ ] Run scripts/run_workflow.py check on this directory.
- [ ] Run scripts/run_workflow.py finalize on this directory before delivery.
""",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create article workflow packet")
    parser.add_argument("--source", required=True, help="Markdown source draft")
    parser.add_argument("--out", required=True, help="Output workflow directory")
    parser.add_argument("--mode", default="rewrite", choices=["diagnostic", "planning", "rewrite", "full-package"])
    parser.add_argument("--platform", default="unspecified")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        parser.error(f"source not found: {source}")
    build_packet(source, Path(args.out).resolve(), args.mode, args.platform)
    print(f"Created workflow packet: {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
