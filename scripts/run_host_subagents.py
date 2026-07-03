#!/usr/bin/env python3
"""Run host-provided subagent commands and record signed workflow evidence."""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
from pathlib import Path
from string import Formatter
from typing import Any

from adapt_codex_subagent_event import extract_runtime_agent_id
from workflow_runtime import (
    AGENT_ROLES,
    RUNTIME_AGENT_ID_RE,
    append_event,
    read_json,
    sha256_file,
)


ALLOWED_PLACEHOLDERS = {
    "workflow_dir",
    "role",
    "task",
    "output",
    "raw_event",
}


def command_placeholders(command_template: str) -> set[str]:
    placeholders: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(command_template):
        if field_name:
            placeholders.add(field_name)
    return placeholders


def format_command(command_template: str, values: dict[str, str]) -> list[str]:
    unknown = command_placeholders(command_template) - ALLOWED_PLACEHOLDERS
    if unknown:
        raise SystemExit("unknown command placeholder(s): " + ", ".join(sorted(unknown)))
    return shlex.split(command_template.format_map(values))


def run_subprocess(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, env=env)


def print_process_failure(role: str, stage: str, result: subprocess.CompletedProcess[str]) -> None:
    print(f"{stage} failed for {role}: exit={result.returncode}", file=sys.stderr)
    if result.stdout.strip():
        print(result.stdout.strip(), file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def run_role(
    root: Path,
    role: str,
    command_template: str,
    runtime_provider: str,
    require_signature: bool,
    signature_key_env: str,
) -> dict[str, Any]:
    task_path = root / "agent_tasks" / f"{role}.md"
    output_path = root / "agent_outputs" / f"{role}.md"
    raw_event_path = root / "runtime_host_events" / f"{role}.json"
    raw_event_path.parent.mkdir(parents=True, exist_ok=True)

    if not task_path.exists():
        raise SystemExit(f"agent task missing for {role}: {task_path}")

    values = {
        "workflow_dir": str(root),
        "role": role,
        "task": str(task_path),
        "output": str(output_path),
        "raw_event": str(raw_event_path),
    }
    command = format_command(command_template, values)
    env = os.environ.copy()
    env.update(
        {
            "PWA_WORKFLOW_DIR": str(root),
            "PWA_ROLE": role,
            "PWA_AGENT_TASK": str(task_path),
            "PWA_AGENT_OUTPUT": str(output_path),
            "PWA_RAW_EVENT": str(raw_event_path),
            "PWA_RUNTIME_PROVIDER": runtime_provider,
        }
    )

    result = run_subprocess(command, env)
    append_event(
        root,
        "host_subagent_command_completed",
        {
            "role": role,
            "exit_code": result.returncode,
            "command_sha256": hashlib.sha256(" ".join(command).encode("utf-8")).hexdigest(),
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        },
    )
    if result.returncode != 0:
        print_process_failure(role, "host subagent command", result)
        raise SystemExit(result.returncode)
    if not output_path.exists():
        raise SystemExit(f"host subagent did not write output for {role}: {output_path}")
    if not raw_event_path.exists():
        raise SystemExit(f"host subagent did not write raw event for {role}: {raw_event_path}")

    raw_payload = read_json(raw_event_path)
    runtime_agent_id = extract_runtime_agent_id(raw_payload)
    if not RUNTIME_AGENT_ID_RE.match(runtime_agent_id):
        raise SystemExit(f"host subagent returned non UUID-like runtime id for {role}")

    adapter_command = [
        sys.executable,
        str(Path(__file__).with_name("adapt_codex_subagent_event.py")),
        "--workflow-dir",
        str(root),
        "--role",
        role,
        "--raw-event",
        str(raw_event_path),
        "--runtime-agent-id",
        runtime_agent_id,
        "--runtime-provider",
        runtime_provider,
    ]
    if require_signature:
        adapter_command.extend(["--require-signature", "--signature-key-env", signature_key_env])
    adapter_result = run_subprocess(adapter_command, os.environ.copy())
    if adapter_result.returncode != 0:
        print_process_failure(role, "runtime event adapter", adapter_result)
        raise SystemExit(adapter_result.returncode)
    runtime_event = adapter_result.stdout.strip().splitlines()[-1]

    record_command = [
        sys.executable,
        str(Path(__file__).with_name("run_workflow.py")),
        "record-agent",
        str(root),
        "--role",
        role,
        "--mode",
        "subagent",
        "--runtime-agent-id",
        runtime_agent_id,
        "--runtime-event",
        runtime_event,
    ]
    record_result = run_subprocess(record_command, os.environ.copy())
    if record_result.returncode != 0:
        print_process_failure(role, "record-agent", record_result)
        raise SystemExit(record_result.returncode)

    return {
        "role": role,
        "runtime_agent_id": runtime_agent_id,
        "output": str(output_path),
        "output_sha256": sha256_file(output_path),
        "raw_event": str(raw_event_path),
        "raw_event_sha256": sha256_file(raw_event_path),
        "runtime_event": runtime_event,
    }


def command_run(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    if not root.exists():
        raise SystemExit(f"workflow dir not found: {root}")
    command_template = args.command or os.environ.get("PWA_SUBAGENT_COMMAND", "")
    if not command_template:
        raise SystemExit("missing --command or PWA_SUBAGENT_COMMAND")
    roles = args.roles or AGENT_ROLES
    unknown_roles = [role for role in roles if role not in AGENT_ROLES]
    if unknown_roles:
        raise SystemExit("unknown role(s): " + ", ".join(unknown_roles))
    if args.require_signature and not os.environ.get(args.signature_key_env, ""):
        raise SystemExit(f"missing signature key env var: {args.signature_key_env}")

    append_event(
        root,
        "host_subagents_started",
        {
            "roles": roles,
            "runtime_provider": args.runtime_provider,
            "require_signature": args.require_signature,
            "command_template_sha256": hashlib.sha256(command_template.encode("utf-8")).hexdigest(),
        },
    )
    summaries = [
        run_role(
            root,
            role,
            command_template,
            args.runtime_provider,
            args.require_signature,
            args.signature_key_env,
        )
        for role in roles
    ]
    append_event(
        root,
        "host_subagents_recorded",
        {
            "roles": roles,
            "runtime_provider": args.runtime_provider,
            "require_signature": args.require_signature,
            "recorded_count": len(summaries),
        },
    )
    for summary in summaries:
        print(f"Recorded host subagent {summary['role']}: {summary['runtime_agent_id']}")

    if args.finalize:
        finalize_command = [
            sys.executable,
            str(Path(__file__).with_name("run_workflow.py")),
            "finalize",
            str(root),
        ]
        if args.require_signature:
            finalize_command.extend(["--require-signed-runtime-events", "--signature-key-env", args.signature_key_env])
        finalize_result = run_subprocess(finalize_command, os.environ.copy())
        if finalize_result.stdout.strip():
            print(finalize_result.stdout.strip())
        if finalize_result.stderr.strip():
            print(finalize_result.stderr.strip(), file=sys.stderr)
        if finalize_result.returncode != 0:
            raise SystemExit(finalize_result.returncode)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and record host-provided subagents")
    parser.add_argument("workflow_dir")
    parser.add_argument(
        "--command",
        default="",
        help=(
            "Host subagent command template. Supports placeholders: "
            "{workflow_dir}, {role}, {task}, {output}, {raw_event}. "
            "The command must write the output Markdown and raw event JSON."
        ),
    )
    parser.add_argument("--roles", nargs="+", choices=AGENT_ROLES)
    parser.add_argument("--runtime-provider", default="host-subagent")
    parser.add_argument("--require-signature", action="store_true")
    parser.add_argument("--signature-key-env", default="PWA_RUNTIME_SIGNING_KEY")
    parser.add_argument("--finalize", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    return command_run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
