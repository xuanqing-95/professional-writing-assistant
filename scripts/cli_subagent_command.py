#!/usr/bin/env python3
"""Host command adapter for CLI-based subagent runtimes."""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

from workflow_runtime import sign_runtime_payload, utc_now, write_json


def strip_existing_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text.strip()
    end = text.find("\n---", 4)
    if end == -1:
        return text.strip()
    return text[end + 4 :].strip()


def build_prompt(role: str, task_text: str) -> str:
    return f"""You are running as the `{role}` expert for a Professional Writing Assistant workflow.

Return only your expert output in Markdown. Do not wrap it in code fences. Do not write workflow metadata frontmatter.

Task:

{task_text}
"""


def command_run(args: argparse.Namespace) -> int:
    task_path = Path(args.task).resolve()
    output_path = Path(args.output).resolve()
    raw_event_path = Path(args.raw_event).resolve()
    command_template = args.command or os.environ.get("PWA_CLI_SUBAGENT_COMMAND", "")
    if not command_template:
        raise SystemExit("missing --command or PWA_CLI_SUBAGENT_COMMAND")
    if not task_path.exists():
        raise SystemExit(f"task file not found: {task_path}")
    if args.sign and not os.environ.get(args.signature_key_env, ""):
        raise SystemExit(f"missing signature key env var: {args.signature_key_env}")

    task_text = task_path.read_text(encoding="utf-8")
    prompt = build_prompt(args.role, task_text)
    command = shlex.split(command_template)
    started_at = utc_now()
    result = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        timeout=args.timeout,
        env=os.environ.copy(),
    )
    completed_at = utc_now()
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)

    completed = strip_existing_frontmatter(result.stdout)
    if not completed:
        raise SystemExit("CLI subagent command returned empty stdout")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"---\nagent: {args.role}\nmode: subagent\n---\n\n{completed}\n",
        encoding="utf-8",
    )

    raw_payload = {
        "agent_path": args.runtime_agent_id or str(uuid.uuid4()),
        "runtime_provider": args.runtime_provider,
        "role": args.role,
        "started_at": started_at,
        "completed_at": completed_at,
        "command_sha256": hashlib.sha256(" ".join(command).encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "status": {
            "completed": completed,
            "exit_code": result.returncode,
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        },
    }
    if args.sign:
        raw_payload["runtime_signature"] = sign_runtime_payload(
            raw_payload,
            os.environ.get(args.signature_key_env, ""),
            key_id=args.signature_key_id,
        )

    raw_event_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(raw_event_path, raw_payload)
    print(raw_event_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a CLI subagent command and write PWA host artifacts")
    parser.add_argument("--role", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-event", required=True)
    parser.add_argument("--command", default="", help="CLI command to run. The task prompt is passed on stdin.")
    parser.add_argument("--runtime-provider", default="cli-subagent")
    parser.add_argument("--runtime-agent-id", default="")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--signature-key-env", default="PWA_RUNTIME_SIGNING_KEY")
    parser.add_argument("--signature-key-id", default="cli-host-key")
    return parser


def main() -> int:
    parser = build_parser()
    return command_run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
