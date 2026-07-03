#!/usr/bin/env python3
"""Smoke tests for runner provenance gates.

These tests intentionally use subprocesses instead of importing internals so they
exercise the same CLI path users run.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_runtime import AGENT_ROLES as ROLES  # noqa: E402

SOURCE = ROOT / "tests" / "fixtures" / "minimal_source.md"


ARTICLE = """# 我第一次用 AI 做项目复盘

上周，我被一个项目复盘卡住了。

我原本以为问题是材料太散，后来发现真正的问题是：我没有先把任务讲清楚。

## 我后来怎么做

后来我让 AI 先帮我拆三件事：项目到底解决什么问题，哪些证据能证明变化，哪些结论只能算我的个人判断。

这个过程不复杂，但它让我意识到，AI 不是直接替我写文章，而是先帮我把经验变成可以讨论的结构。

## 我能复用的方法

最后我留下了一个简单方法：先锁定事实，再整理判断，最后再写正文。
"""


def run(command: list[str], cwd: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=check)


def prepare(tmp: Path) -> Path:
    workflow = tmp / "workflow"
    run(
        [
            sys.executable,
            "scripts/run_workflow.py",
            "prepare",
            "--source",
            str(SOURCE),
            "--out",
            str(workflow),
            "--mode",
            "rewrite",
            "--platform",
            "wechat",
        ],
        check=True,
    )
    return workflow


def fill_workflow(workflow: Path, agent_mode: str = "simulated") -> None:
    for path in workflow.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"<!-- REQUIRED:.*?-->", "filled", text, flags=re.S)
        path.write_text(text, encoding="utf-8")

    for path in (workflow / "agent_outputs").glob("*.md"):
        role = path.stem
        path.write_text(
            f"---\nagent: {role}\nmode: {agent_mode}\n---\n\n# {role}\n\nfilled\n",
            encoding="utf-8",
        )

    (workflow / "07b_source_fidelity_review.md").write_text(
        "# 07b Source Fidelity Review\n\n## Meaning Preservation Verdict\n\npass\n",
        encoding="utf-8",
    )
    (workflow / "final_publish_article.md").write_text(ARTICLE, encoding="utf-8")
    (workflow / "09_final_article.md").write_text(
        f"""# 09 Final Article

## Title Options
1. title
2. title
3. title

## Final Article
{ARTICLE}

## Image Placement Notes
No images.

## Screenshot-Worthy Lines
1. line
2. line
3. line

## Reusable Reader Component
filled

## Credibility Notes
filled
""",
        encoding="utf-8",
    )
    checklist = (workflow / "10_workflow_checklist.md").read_text(encoding="utf-8")
    (workflow / "10_workflow_checklist.md").write_text(
        checklist.replace("- [ ]", "- [x]"),
        encoding="utf-8",
    )


def check_workflow(workflow: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "scripts/check_workflow_output.py",
            str(workflow),
            "--require-runner",
        ]
    )


def test_filled_workflow_without_runner_agent_records_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow)
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "runner has no recorded agent output" in result.stdout


def test_recorded_simulated_workflow_passes_with_warnings() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow)
        for role in ROLES:
            run(
                [
                    sys.executable,
                    "scripts/run_workflow.py",
                    "record-agent",
                    str(workflow),
                    "--role",
                    role,
                    "--mode",
                    "simulated",
                ],
                check=True,
            )
        result = check_workflow(workflow)
        assert result.returncode == 0
        assert "WARN simulated expert output" in result.stdout


def test_claimed_subagent_without_runtime_id_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow, agent_mode="subagent")
        result = run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "record-agent",
                str(workflow),
                "--role",
                ROLES[0],
                "--mode",
                "subagent",
            ],
        )
        assert result.returncode != 0
        assert "requires --runtime-agent-id" in result.stderr


def record_all_simulated(workflow: Path) -> None:
    for role in ROLES:
        run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "record-agent",
                str(workflow),
                "--role",
                role,
                "--mode",
                "simulated",
            ],
            check=True,
        )


def test_tampered_agent_output_after_record_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow)
        record_all_simulated(workflow)
        output = workflow / "agent_outputs" / "strategist.md"
        output.write_text(output.read_text(encoding="utf-8") + "\nTampered after recording.\n", encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "agent output hash mismatch for strategist" in result.stdout


def test_tampered_source_after_prepare_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow)
        record_all_simulated(workflow)
        source = workflow / "00_source.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nTampered source.\n", encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "00_source.md hash does not match" in result.stdout


def test_tampered_runner_log_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow)
        record_all_simulated(workflow)
        log = workflow / "logs" / "run_log.jsonl"
        text = log.read_text(encoding="utf-8")
        log.write_text(text.replace("run_prepared", "run_prepared_tampered", 1), encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "invalid event_hash" in result.stdout or "missing run_prepared" in result.stdout


def test_record_agent_rejects_frontmatter_mode_mismatch() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow, agent_mode="simulated")
        result = run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "record-agent",
                str(workflow),
                "--role",
                "strategist",
                "--mode",
                "subagent",
                "--runtime-agent-id",
                "fake-runtime-id",
            ],
        )
        assert result.returncode != 0
        assert "agent output mode mismatch" in result.stderr


def test_record_agent_rejects_invalid_runtime_id_format() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow, agent_mode="subagent")
        result = run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "record-agent",
                str(workflow),
                "--role",
                "strategist",
                "--mode",
                "subagent",
                "--runtime-agent-id",
                "fake-runtime-id",
            ],
        )
        assert result.returncode != 0
        assert "UUID-like runtime id" in result.stderr


def test_claimed_subagent_with_uuid_runtime_id_still_passes_as_unsigned_proof() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        workflow = prepare(Path(dirname))
        fill_workflow(workflow, agent_mode="subagent")
        for index, role in enumerate(ROLES, 1):
            run(
                [
                    sys.executable,
                    "scripts/run_workflow.py",
                    "record-agent",
                    str(workflow),
                    "--role",
                    role,
                    "--mode",
                    "subagent",
                    "--runtime-agent-id",
                    f"019f27cd-0000-7000-8000-{index:012d}",
                ],
                check=True,
            )
        result = check_workflow(workflow)
        assert result.returncode == 0


if __name__ == "__main__":
    for test in [
        test_filled_workflow_without_runner_agent_records_fails,
        test_recorded_simulated_workflow_passes_with_warnings,
        test_claimed_subagent_without_runtime_id_fails,
        test_tampered_agent_output_after_record_fails,
        test_tampered_source_after_prepare_fails,
        test_tampered_runner_log_fails,
        test_record_agent_rejects_frontmatter_mode_mismatch,
        test_record_agent_rejects_invalid_runtime_id_format,
        test_claimed_subagent_with_uuid_runtime_id_still_passes_as_unsigned_proof,
    ]:
        test()
    print("runner tests passed")
