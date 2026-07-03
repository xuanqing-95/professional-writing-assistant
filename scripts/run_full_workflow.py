#!/usr/bin/env python3
"""Run an end-to-end Professional Writing Assistant workflow with a model CLI."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from workflow_runtime import AGENT_ROLES


ROOT = Path(__file__).resolve().parents[1]

ARTIFACT_ORDER = [
    "00_media_manifest.md",
    "00_source_claim_map.md",
    "01_intake_diagnosis.md",
    "02_strategy_brief.md",
    "03_interview_gaps.md",
    "04a_author_voice_profile.md",
    "04_structure_review.md",
    "04b_narrative_review.md",
    "05_value_review.md",
    "06_spread_review.md",
    "07_credibility_review.md",
    "08_rewrite_plan.md",
    "09_final_article.md",
    "final_publish_article.md",
    "07b_source_fidelity_review.md",
]

PLACEHOLDER_RE = re.compile(r"<!-- REQUIRED:.*?-->", re.DOTALL)


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=full_env)


def run_or_fail(command: list[str], *, env: dict[str, str] | None = None) -> None:
    result = run(command, env=env)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())


def run_model_command(command_template: str, prompt: str, timeout: int, env: dict[str, str]) -> str:
    command = shlex.split(command_template)
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ.copy(), **env},
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    output = result.stdout.strip()
    if not output:
        raise SystemExit("model command returned empty output")
    return output


def read_if_exists(path: Path, max_chars: int = 60000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]\n"


def artifact_prompt(workflow: Path, artifact: str) -> str:
    source = read_if_exists(workflow / "00_source.md")
    voice_seed = read_if_exists(workflow / "00_author_voice_seed.md")
    media = read_if_exists(workflow / "00_media_manifest.md")
    claim_map = read_if_exists(workflow / "00_source_claim_map.md")
    agent_outputs = []
    for role in AGENT_ROLES:
        path = workflow / "agent_outputs" / f"{role}.md"
        if path.exists():
            agent_outputs.append(f"## {role}\n\n{read_if_exists(path, 12000)}")

    current = read_if_exists(workflow / artifact)
    return f"""You are completing a Professional Writing Assistant workflow artifact.

Write only the complete Markdown content for `{artifact}`. Do not wrap it in fences.
Do not leave REQUIRED placeholders. Do not invent facts, numbers, quotes, images, or personal experiences.
Use Chinese by default unless the source is not Chinese.

Artifact-specific rules:
- `00_source_claim_map.md`: lock exact facts, core claims, causal logic, boundaries, allowed changes, and forbidden changes from the source.
- `04a_author_voice_profile.md`: include `Evidence:` lines in Signature Phrases / Moves, Preserve, Do Not Introduce, and Migration Rules.
- `final_publish_article.md`: write publish-ready body only. Do not include internal sections like Image Placement Notes, Screenshot-Worthy Lines, Reusable Reader Component, or Credibility Notes.
- `07b_source_fidelity_review.md`: compare the final article with the source claim map. Use verdict `pass` only if no material meaning drift remains.

# Current Artifact Template

{current}

# Source Draft

{source}

# Author Voice Seed

{voice_seed}

# Media Manifest

{media}

# Source Claim Map

{claim_map}

# Agent Outputs

{chr(10).join(agent_outputs)}
"""


def write_artifact_from_model(workflow: Path, artifact: str, model_command: str, timeout: int) -> None:
    path = workflow / artifact
    if not path.exists():
        return
    if artifact == "00_media_manifest.md" and "No source images detected." in path.read_text(encoding="utf-8"):
        return
    prompt = artifact_prompt(workflow, artifact)
    output = run_model_command(
        model_command,
        prompt,
        timeout,
        {
            "PWA_WORKFLOW_DIR": str(workflow),
            "PWA_ARTIFACT": artifact,
        },
    )
    path.write_text(output.rstrip() + "\n", encoding="utf-8")


def write_simulated_agent_outputs(workflow: Path, model_command: str, timeout: int) -> None:
    for role in AGENT_ROLES:
        task_path = workflow / "agent_tasks" / f"{role}.md"
        output_path = workflow / "agent_outputs" / f"{role}.md"
        prompt = f"""Complete this Professional Writing Assistant expert task.

Return Markdown content for the role output body only. Ground every recommendation in the source and task.

# Task

{read_if_exists(task_path)}
"""
        body = run_model_command(
            model_command,
            prompt,
            timeout,
            {
                "PWA_WORKFLOW_DIR": str(workflow),
                "PWA_ROLE": role,
                "PWA_ARTIFACT": f"agent_outputs/{role}.md",
            },
        )
        output_path.write_text(
            f"---\nagent: {role}\nmode: simulated\n---\n\n{body.rstrip()}\n",
            encoding="utf-8",
        )
        run_or_fail(
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


def run_host_agents(args: argparse.Namespace, workflow: Path) -> None:
    command = [
        sys.executable,
        "scripts/run_host_subagents.py",
        str(workflow),
        "--command",
        args.agent_command,
        "--runtime-provider",
        args.runtime_provider,
    ]
    if args.require_signature:
        command.append("--require-signature")
        command.extend(["--signature-key-env", args.signature_key_env])
    run_or_fail(command)


def complete_checklist(workflow: Path) -> None:
    checklist = workflow / "10_workflow_checklist.md"
    if not checklist.exists():
        return
    text = checklist.read_text(encoding="utf-8")
    checklist.write_text(text.replace("- [ ]", "- [x]"), encoding="utf-8")


def ensure_no_placeholders(workflow: Path) -> None:
    remaining = []
    for path in workflow.rglob("*.md"):
        if PLACEHOLDER_RE.search(path.read_text(encoding="utf-8")):
            remaining.append(path.relative_to(workflow).as_posix())
    if remaining:
        raise SystemExit("workflow still has REQUIRED placeholders:\n- " + "\n- ".join(remaining))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a complete PWA workflow with a model CLI")
    parser.add_argument("--source", required=True, help="Source Markdown")
    parser.add_argument("--out", required=True, help="Workflow output directory")
    parser.add_argument("--model-command", required=True, help="CLI command that reads prompt from stdin and writes Markdown to stdout")
    parser.add_argument("--mode", default="rewrite", choices=["diagnostic", "planning", "rewrite", "full-package"])
    parser.add_argument("--platform", default="wechat")
    parser.add_argument("--agent-command", default="", help="Optional real subagent host command. If omitted, expert outputs are generated as simulated.")
    parser.add_argument("--runtime-provider", default="host-subagent")
    parser.add_argument("--require-signature", action="store_true")
    parser.add_argument("--signature-key-env", default="PWA_RUNTIME_SIGNING_KEY")
    parser.add_argument("--require-signed-runtime-events", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    source = Path(args.source).resolve()
    workflow = Path(args.out).resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")
    if workflow.exists() and args.force:
        shutil.rmtree(workflow)
    elif workflow.exists() and any(workflow.iterdir()):
        raise SystemExit(f"workflow dir is not empty: {workflow}. Use --force to replace it.")
    if args.require_signed_runtime_events and not args.agent_command:
        raise SystemExit("--require-signed-runtime-events requires --agent-command")

    prepare = [
        sys.executable,
        "scripts/run_workflow.py",
        "prepare",
        "--source",
        str(source),
        "--out",
        str(workflow),
        "--mode",
        args.mode,
        "--platform",
        args.platform,
    ]
    if args.force:
        prepare.append("--force")
    run_or_fail(prepare)

    if args.agent_command:
        run_host_agents(args, workflow)
    else:
        write_simulated_agent_outputs(workflow, args.model_command, args.timeout)

    for artifact in ARTIFACT_ORDER:
        write_artifact_from_model(workflow, artifact, args.model_command, args.timeout)
    complete_checklist(workflow)
    ensure_no_placeholders(workflow)

    finalize = [sys.executable, "scripts/run_workflow.py", "finalize", str(workflow)]
    env = None
    if args.require_signed_runtime_events:
        finalize.append("--require-signed-runtime-events")
        finalize.extend(["--signature-key-env", args.signature_key_env])
        env = {args.signature_key_env: os.environ.get(args.signature_key_env, "")}
    run_or_fail(finalize, env=env)
    print(f"Full workflow: {workflow}")
    print(f"Publish article: {workflow / 'final_publish_article.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
