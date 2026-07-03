#!/usr/bin/env python3
"""Fake model for end-to-end workflow orchestration tests."""

from __future__ import annotations

import os
import sys


ARTICLE = """# 我第一次用 AI 做项目复盘

上周，我被一个项目复盘卡住了。

我原本以为问题是材料太散，后来发现真正的问题不是材料，而是我还没有把任务讲清楚。

后来我让 AI 先帮我拆三件事：项目到底解决什么问题，哪些证据能证明变化，哪些结论只能算我的个人判断。

这个过程不复杂，但它让我意识到，AI 不是直接替我写文章，而是先帮我把经验变成可以讨论的结构。

我最后留下了一个简单方法：先锁定事实，再整理判断，最后再写正文。

这次之后，我对 AI 写作的理解更保守了。它最有用的地方，不是替我把话说漂亮，而是让我先看清楚自己经历了什么、能负责地说到哪里。
"""


def artifact_output(artifact: str) -> str:
    if artifact.startswith("agent_outputs/"):
        role = os.environ.get("PWA_ROLE", "unknown")
        return f"# {role}\n\nSimulated expert review grounded in the source.\n"
    if artifact == "00_source_claim_map.md":
        return """# 00 Source Claim Map

## Non-Negotiable Facts
1. The author was stuck on a project recap.
2. The author first thought the problem was scattered material.
3. The author later found the real issue was not clarifying the task first.

## Core Claims
1. AI helped structure the experience before writing.
2. The useful sequence is fact first, judgment second, article third.
3. AI did not replace the author's judgment.

## Causal Logic
- Because: the author separated task, evidence, and personal judgment.
- Therefore: the recap became easier to write responsibly.
- Not because: AI produced expertise on its own.

## Experience Boundaries
- Works when: the author has real source experience.
- Does not prove: every AI writing workflow works this way.
- Needs author verification: none in this fixture.

## Allowed Changes
- Structure: split compact source into readable paragraphs.
- Language: light smoothing.
- Additions: connective tissue already implied by source.

## Forbidden Changes
1. Do not claim AI completed the project independently.
2. Do not turn one recap into a universal law.
3. Do not remove the author's uncertainty.
"""
    if artifact == "04a_author_voice_profile.md":
        return """# 04a Author Voice Profile

## Voice Fingerprint
First-person practical reflection from stuck to clearer.

## Thinking Lens
The author understands writing as clarifying task, evidence, and judgment.

## Sentence Rhythm
Short paragraphs with a turn from first assumption to later discovery.

## Signature Phrases / Moves
- Move from first assumption to later discovery. Evidence: "我原本以为问题是材料太散，后来发现..."
- Keep the AI writing boundary. Evidence: "AI 不是直接替我写文章..."

## Preserve
- Preserve first-person practical uncertainty. Evidence: "我被一个项目复盘卡住了。"
- Preserve cautious claims. Evidence: "哪些结论只能算我的个人判断。"

## Clean Up
- Compress repetition without changing sequence.

## Do Not Introduce
- Do not introduce universal AI claims. Evidence: source describes one recap.
- Do not introduce motivational platform language. Evidence: source is plain and practical.

## Migration Rules
- Keep source sequence: stuck -> wrong assumption -> AI-assisted structure -> simple method. Evidence: this order appears in source.
- Keep first-person framing. Evidence: source repeatedly uses "我".

## Voice Check
The article should read like the same author, only clearer.
"""
    if artifact == "09_final_article.md":
        return f"""# 09 Final Article

## Title Options
1. 我第一次用 AI 做项目复盘
2. AI 没有替我写复盘，它先帮我看清任务
3. 项目复盘卡住时，我让 AI 先拆了三件事

## Final Article
{ARTICLE}

## Image Placement Notes
No source images.

## Screenshot-Worthy Lines
1. AI 不是直接替我写文章，而是先帮我把经验变成可以讨论的结构。
2. 先锁定事实，再整理判断，最后再写正文。
3. 不要把个人感受写成确定结论。

## Reusable Reader Component
Fact first, judgment second, article third.

## Credibility Notes
Keep this as one personal experience.
"""
    if artifact == "final_publish_article.md":
        return ARTICLE
    if artifact == "07b_source_fidelity_review.md":
        return """# 07b Source Fidelity Review

## Meaning Preservation Verdict

pass

## Changed Meaning Risks
No material drift remains.

## Facts That Must Stay Exact
The author was stuck on a project recap and used AI to structure task, evidence, and personal judgment.

## Claims That Must Be Softened
Do not imply AI replaced the author's judgment.

## Additions Requiring Author Verification
None.

## Required Fixes Before Final
None.
"""
    titles = {
        "01_intake_diagnosis.md": "01 Intake Diagnosis",
        "02_strategy_brief.md": "02 Strategy Brief",
        "03_interview_gaps.md": "03 Interview Gaps",
        "04_structure_review.md": "04 Structure Review",
        "04b_narrative_review.md": "04b Narrative Review",
        "05_value_review.md": "05 Reader Value Review",
        "06_spread_review.md": "06 Spread Review",
        "07_credibility_review.md": "07 Credibility Review",
        "08_rewrite_plan.md": "08 Rewrite Plan",
    }
    title = titles.get(artifact, artifact)
    return f"# {title}\n\nCompleted fixture content grounded in the source.\n"


def main() -> int:
    _prompt = sys.stdin.read()
    artifact = os.environ.get("PWA_ARTIFACT", "")
    print(artifact_output(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
