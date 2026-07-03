#!/usr/bin/env python3
"""Run a local simulated quickstart workflow for Professional Writing Assistant."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from workflow_runtime import AGENT_ROLES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "examples" / "quickstart-source.md"

ARTICLE = """# 我第一次用 AI 做项目复盘

上周，我被一个项目复盘卡住了。

我原本以为问题是材料太散，后来发现真正的问题不是材料，而是我还没有把任务讲清楚。

后来我让 AI 先帮我拆三件事：项目到底解决什么问题，哪些证据能证明变化，哪些结论只能算我的个人判断。

这个过程不复杂，但它把我从“直接写正文”的惯性里拉了出来。我发现，AI 不是直接替我写文章，而是先帮我把经验变成可以讨论的结构。

我最后留下了一个简单方法：

先锁定事实。哪些事情确实发生了，哪些结果真的能被证据支持。

再整理判断。哪些是我从项目里得到的理解，哪些只是暂时的猜测。

最后再写正文。这样写出来的复盘，不只是更顺，也更不容易把个人感受写成确定结论。

这次之后，我对 AI 写作的理解变得更保守了一点。它最有用的地方，不是替我把话说漂亮，而是让我先看清楚：我到底经历了什么，我能负责地说到哪里。
"""


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=env)


def replace_required_blocks(path: Path, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!-- REQUIRED:.*?-->", value, text, flags=re.DOTALL)
    path.write_text(text, encoding="utf-8")


def write_agent_outputs(workflow: Path) -> None:
    for role in AGENT_ROLES:
        (workflow / "agent_outputs" / f"{role}.md").write_text(
            f"---\nagent: {role}\nmode: simulated\n---\n\n# {role}\n\nDemo simulated review completed for quickstart.\n",
            encoding="utf-8",
        )


def complete_packet(workflow: Path) -> None:
    for path in workflow.rglob("*.md"):
        replace_required_blocks(path, "Demo completed.")

    (workflow / "00_source_claim_map.md").write_text(
        """# 00 Source Claim Map

## Non-Negotiable Facts
1. The author was stuck on a project recap.
2. The author first thought the problem was scattered material.
3. The author later found the real issue was not clarifying the task first.

## Core Claims
1. AI helped the author structure the experience before writing.
2. The useful workflow is fact first, judgment second, article third.
3. The result is a more discussable and responsible recap, not automatic expertise.

## Causal Logic
- Because: the author separated task, evidence, and personal judgment.
- Therefore: the recap became easier to write and less likely to overclaim.
- Not because: AI magically made the author an expert.

## Experience Boundaries
- Works when: the author has real source experience to organize.
- Does not prove: AI can replace source material, evidence, or author judgment.
- Needs author verification: none for this demo.

## Allowed Changes
- Structure: split the compact source into scan-friendly article sections.
- Language: lightly smooth wording.
- Additions: only connective tissue already implied by the source.

## Forbidden Changes
1. Do not claim AI completed the project independently.
2. Do not turn one recap into a universal law.
3. Do not remove the author's uncertainty.
""",
        encoding="utf-8",
    )

    (workflow / "04a_author_voice_profile.md").write_text(
        """# 04a Author Voice Profile

## Voice Fingerprint
First-person practical reflection. The author starts from being stuck, then corrects an initial assumption.

## Thinking Lens
The author understands writing as clarifying task, evidence, and judgment.

## Sentence Rhythm
Short paragraphs, direct first-person statements, and a turn from misconception to later realization.

## Signature Phrases / Moves
- Move from first assumption to later discovery. Evidence: "我原本以为问题是材料太散，后来发现..."
- Keep the "AI is not directly writing for me" boundary. Evidence: "AI 不是直接替我写文章..."

## Preserve
- Preserve the first-person working-through tone. Evidence: "我被一个项目复盘卡住了。"
- Preserve cautious judgment rather than expert certainty. Evidence: "哪些结论只能算我的个人判断。"

## Clean Up
- Reduce compact repetition without removing the author's sequence.

## Do Not Introduce
- Do not introduce universal claims about AI writing. Evidence: the source only describes one project recap.
- Do not introduce motivational platform language. Evidence: the source is plain and practical.

## Migration Rules
- Keep the source sequence: stuck -> wrong assumption -> AI-assisted structure -> simple method. Evidence: each step appears in source order.
- Keep "我" as the speaker. Evidence: the source repeatedly uses first-person framing.

## Voice Check
The final article should still sound like the same author explaining a small practical discovery.
""",
        encoding="utf-8",
    )

    (workflow / "07b_source_fidelity_review.md").write_text(
        """# 07b Source Fidelity Review

## Meaning Preservation Verdict

pass

## Changed Meaning Risks
None material. The article keeps the same facts, sequence, and boundary.

## Facts That Must Stay Exact
The author was stuck on a project recap and used AI to structure task, evidence, and personal judgment.

## Claims That Must Be Softened
Do not imply AI replaced the author's judgment.

## Additions Requiring Author Verification
None for this demo.

## Required Fixes Before Final
None.
""",
        encoding="utf-8",
    )

    (workflow / "final_publish_article.md").write_text(ARTICLE, encoding="utf-8")
    (workflow / "09_final_article.md").write_text(
        f"""# 09 Final Article

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
The article keeps this as one personal experience, not a universal claim.
""",
        encoding="utf-8",
    )

    checklist = (workflow / "10_workflow_checklist.md").read_text(encoding="utf-8")
    (workflow / "10_workflow_checklist.md").write_text(checklist.replace("- [ ]", "- [x]"), encoding="utf-8")
    write_agent_outputs(workflow)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a simulated PWA quickstart workflow")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Source Markdown to use")
    parser.add_argument("--out", default="", help="Workflow output directory. Defaults to a temp directory.")
    parser.add_argument("--force", action="store_true", help="Remove an existing --out directory before running")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")

    if args.out:
        workflow = Path(args.out).resolve()
        if workflow.exists() and args.force:
            shutil.rmtree(workflow)
        elif workflow.exists() and any(workflow.iterdir()):
            raise SystemExit(f"output directory is not empty: {workflow}. Use --force to replace it.")
    else:
        workflow = Path(tempfile.mkdtemp(prefix="pwa-quickstart-")) / "workflow"

    result = run(
        [
            sys.executable,
            "scripts/run_workflow.py",
            "prepare",
            "--source",
            str(source),
            "--out",
            str(workflow),
            "--mode",
            "rewrite",
            "--platform",
            "wechat",
        ]
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    complete_packet(workflow)

    for role in AGENT_ROLES:
        record = run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "record-agent",
                str(workflow),
                "--role",
                role,
                "--mode",
                "simulated",
            ]
        )
        if record.returncode != 0:
            print(record.stdout, end="")
            print(record.stderr, end="", file=sys.stderr)
            return record.returncode

    final = run([sys.executable, "scripts/run_workflow.py", "finalize", str(workflow)])
    print(final.stdout, end="")
    if final.stderr:
        print(final.stderr, end="", file=sys.stderr)
    if final.returncode != 0:
        return final.returncode

    print(f"Quickstart workflow: {workflow}")
    print(f"Publish article: {workflow / 'final_publish_article.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
