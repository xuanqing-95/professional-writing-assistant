#!/usr/bin/env python3
"""Smoke tests for runner provenance gates.

These tests intentionally use subprocesses instead of importing internals so they
exercise the same CLI path users run.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_runtime import AGENT_ROLES as ROLES, sign_runtime_payload  # noqa: E402
SOURCE = ROOT / "tests" / "fixtures" / "minimal_source.md"
SIGNING_KEY = "test-host-signing-key"


ARTICLE = """# 我第一次用 AI 做项目复盘

上周，我被一个项目复盘卡住了。

我原本以为问题是材料太散，后来发现真正的问题是：我没有先把任务讲清楚。

## 我后来怎么做

后来我让 AI 先帮我拆三件事：项目到底解决什么问题，哪些证据能证明变化，哪些结论只能算我的个人判断。

这个过程不复杂，但它让我意识到，AI 不是直接替我写文章，而是先帮我把经验变成可以讨论的结构。

## 我能复用的方法

最后我留下了一个简单方法：先锁定事实，再整理判断，最后再写正文。
"""


def run(
    command: list[str],
    cwd: Path = ROOT,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=check, env=full_env)


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


def check_workflow_strict(workflow: Path, signature_key: str = SIGNING_KEY) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "scripts/check_workflow_output.py",
            str(workflow),
            "--require-runner",
            "--require-signed-runtime-events",
        ],
        env={"PWA_RUNTIME_SIGNING_KEY": signature_key},
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


def runtime_id_for(index: int) -> str:
    return f"019f27cd-0000-7000-8000-{index:012d}"


def write_raw_codex_event(
    role: str,
    runtime_agent_id: str,
    event_dir: Path,
    signed: bool = False,
    signing_key: str = SIGNING_KEY,
) -> Path:
    import json

    event_dir.mkdir(parents=True, exist_ok=True)
    event_path = event_dir / f"{role}.raw.json"
    raw_payload = {
        "agent_path": runtime_agent_id,
        "status": {
            "completed": f"# {role}\n\nfilled\n",
        },
    }
    if signed:
        raw_payload["runtime_signature"] = sign_runtime_payload(
            raw_payload,
            signing_key,
            key_id="test-key",
        )
    event_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return event_path


def adapt_runtime_event(
    workflow: Path,
    role: str,
    runtime_agent_id: str,
    event_dir: Path,
    signed: bool = False,
    require_signature: bool = False,
    signing_key: str = SIGNING_KEY,
) -> Path:
    raw_path = write_raw_codex_event(role, runtime_agent_id, event_dir, signed=signed, signing_key=signing_key)
    command = [
        sys.executable,
        "scripts/adapt_codex_subagent_event.py",
        "--workflow-dir",
        str(workflow),
        "--role",
        role,
        "--raw-event",
        str(raw_path),
        "--runtime-agent-id",
        runtime_agent_id,
        "--runtime-provider",
        "codex-test-runtime",
    ]
    env = None
    if require_signature:
        command.append("--require-signature")
        env = {"PWA_RUNTIME_SIGNING_KEY": signing_key}
    result = run(command, check=True, env=env)
    return Path(result.stdout.strip())


def record_all_subagents_with_proofs(
    workflow: Path,
    proof_dir: Path,
    signed: bool = False,
    require_signature: bool = False,
) -> None:
    for index, role in enumerate(ROLES, 1):
        runtime_id = runtime_id_for(index)
        event_path = adapt_runtime_event(
            workflow,
            role,
            runtime_id,
            proof_dir,
            signed=signed,
            require_signature=require_signature,
        )
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
                runtime_id,
                "--runtime-event",
                str(event_path),
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


def test_claimed_subagent_with_uuid_runtime_id_without_proof_fails() -> None:
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
                runtime_id_for(1),
            ],
        )
        assert result.returncode != 0
        assert "requires --runtime-event" in result.stderr


def test_subagent_with_event_generates_proof() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        event_path = adapt_runtime_event(workflow, "strategist", runtime_id_for(1), root / "proofs")
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
                runtime_id_for(1),
                "--runtime-event",
                str(event_path),
            ],
        )
        assert result.returncode == 0
        assert (workflow / "runtime_raw_events" / "strategist.json").exists()
        assert (workflow / "runtime_events" / "strategist.json").exists()
        assert (workflow / "runtime_proofs" / "strategist.json").exists()


def test_subagent_with_runtime_proof_passes() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs")
        result = check_workflow(workflow)
        assert result.returncode == 0


def test_unsigned_subagent_workflow_fails_strict_signature_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs")
        result = check_workflow_strict(workflow)
        assert result.returncode != 0
        assert "lacks verified raw event signature" in result.stdout


def test_signed_subagent_workflow_passes_strict_signature_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs", signed=True, require_signature=True)
        result = check_workflow_strict(workflow)
        assert result.returncode == 0


def test_signed_subagent_workflow_fails_strict_with_wrong_key() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs", signed=True, require_signature=True)
        result = check_workflow_strict(workflow, signature_key="wrong-key")
        assert result.returncode != 0
        assert "signature mismatch" in result.stdout


def test_signed_subagent_workflow_strict_finalize_passes() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs", signed=True, require_signature=True)
        result = run(
            [
                sys.executable,
                "scripts/run_workflow.py",
                "finalize",
                str(workflow),
                "--require-signed-runtime-events",
            ],
            env={"PWA_RUNTIME_SIGNING_KEY": SIGNING_KEY},
        )
        assert result.returncode == 0
        assert "Finalized workflow" in result.stdout


def test_adapter_rejects_unsigned_raw_event_when_signature_required() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        raw_path = write_raw_codex_event("strategist", runtime_id_for(1), root / "proofs")
        result = run(
            [
                sys.executable,
                "scripts/adapt_codex_subagent_event.py",
                "--workflow-dir",
                str(workflow),
                "--role",
                "strategist",
                "--raw-event",
                str(raw_path),
                "--runtime-agent-id",
                runtime_id_for(1),
                "--require-signature",
            ],
            env={"PWA_RUNTIME_SIGNING_KEY": SIGNING_KEY},
        )
        assert result.returncode != 0
        assert "missing runtime_signature" in result.stderr


def host_subagent_command(sign: bool = True) -> str:
    command = (
        f"{sys.executable} tests/fixtures/fake_host_subagent.py "
        "--role {role} --output {output} --raw-event {raw_event}"
    )
    if sign:
        command += " --sign"
    return command


def test_host_supervisor_signed_subagents_strict_finalize_passes() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        result = run(
            [
                sys.executable,
                "scripts/run_host_subagents.py",
                str(workflow),
                "--command",
                host_subagent_command(sign=True),
                "--runtime-provider",
                "fake-host-runtime",
                "--require-signature",
                "--finalize",
            ],
            env={"PWA_RUNTIME_SIGNING_KEY": SIGNING_KEY},
        )
        assert result.returncode == 0
        assert "Finalized workflow" in result.stdout
        assert (workflow / "runtime_proofs" / "strategist.json").exists()
        assert (workflow / "gate_result.json").exists()


def test_host_supervisor_rejects_unsigned_subagent_when_signature_required() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        result = run(
            [
                sys.executable,
                "scripts/run_host_subagents.py",
                str(workflow),
                "--command",
                host_subagent_command(sign=False),
                "--runtime-provider",
                "fake-host-runtime",
                "--require-signature",
            ],
            env={"PWA_RUNTIME_SIGNING_KEY": SIGNING_KEY},
        )
        assert result.returncode != 0
        assert "missing runtime_signature" in result.stderr


def test_host_supervisor_requires_command() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        result = run(
            [
                sys.executable,
                "scripts/run_host_subagents.py",
                str(workflow),
            ],
            env={"PWA_SUBAGENT_COMMAND": ""},
        )
        assert result.returncode != 0
        assert "missing --command" in result.stderr


def test_tampered_runtime_proof_after_record_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs")
        proof = workflow / "runtime_proofs" / "strategist.json"
        proof.write_text(proof.read_text(encoding="utf-8").replace("strategist", "interviewer", 1), encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "runtime proof" in result.stdout


def test_tampered_runtime_event_after_record_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs")
        event = workflow / "runtime_events" / "strategist.json"
        event.write_text(event.read_text(encoding="utf-8").replace("strategist", "interviewer", 1), encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "runtime event" in result.stdout


def test_tampered_raw_runtime_event_after_record_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        record_all_subagents_with_proofs(workflow, root / "proofs")
        raw = workflow / "runtime_raw_events" / "strategist.json"
        raw.write_text(raw.read_text(encoding="utf-8").replace("filled", "tampered", 1), encoding="utf-8")
        result = check_workflow(workflow)
        assert result.returncode != 0
        assert "raw event" in result.stdout


def test_adapter_rejects_output_that_does_not_contain_completed_text() -> None:
    with tempfile.TemporaryDirectory(prefix="pwa-runner-test-") as dirname:
        root = Path(dirname)
        workflow = prepare(root)
        fill_workflow(workflow, agent_mode="subagent")
        raw_path = write_raw_codex_event("strategist", runtime_id_for(1), root / "proofs")
        output = workflow / "agent_outputs" / "strategist.md"
        output.write_text("---\nagent: strategist\nmode: subagent\n---\n\nEdited summary only.\n", encoding="utf-8")
        result = run(
            [
                sys.executable,
                "scripts/adapt_codex_subagent_event.py",
                "--workflow-dir",
                str(workflow),
                "--role",
                "strategist",
                "--raw-event",
                str(raw_path),
                "--runtime-agent-id",
                runtime_id_for(1),
            ],
        )
        assert result.returncode != 0
        assert "paste subagent output verbatim" in result.stderr


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
        test_claimed_subagent_with_uuid_runtime_id_without_proof_fails,
        test_subagent_with_event_generates_proof,
        test_subagent_with_runtime_proof_passes,
        test_unsigned_subagent_workflow_fails_strict_signature_gate,
        test_signed_subagent_workflow_passes_strict_signature_gate,
        test_signed_subagent_workflow_fails_strict_with_wrong_key,
        test_signed_subagent_workflow_strict_finalize_passes,
        test_adapter_rejects_unsigned_raw_event_when_signature_required,
        test_host_supervisor_signed_subagents_strict_finalize_passes,
        test_host_supervisor_rejects_unsigned_subagent_when_signature_required,
        test_host_supervisor_requires_command,
        test_tampered_runtime_proof_after_record_fails,
        test_tampered_runtime_event_after_record_fails,
        test_tampered_raw_runtime_event_after_record_fails,
        test_adapter_rejects_output_that_does_not_contain_completed_text,
    ]:
        test()
    print("runner tests passed")
