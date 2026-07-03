#!/usr/bin/env python3
"""Claude Code CLI adapter for Professional Writing Assistant subagent roles."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from cli_subagent_command import command_run as run_cli_subagent


def resolve_claude_command(args: argparse.Namespace) -> str:
    if args.claude_command:
        return args.claude_command
    command = [
        args.claude_bin,
        "-p",
        "--output-format",
        "text",
        "--no-session-persistence",
        "--permission-mode",
        args.permission_mode,
        "--model",
        args.model,
    ]
    if args.bare:
        command.append("--bare")
    if args.tools:
        command.extend(["--tools", args.tools])
    if args.max_budget_usd:
        command.extend(["--max-budget-usd", args.max_budget_usd])
    if args.append_system_prompt:
        command.extend(["--append-system-prompt", args.append_system_prompt])
    return " ".join(shlex.quote(part) for part in command)


def command_run(args: argparse.Namespace) -> int:
    command = resolve_claude_command(args)
    cli_args = argparse.Namespace(
        role=args.role,
        task=args.task,
        output=args.output,
        raw_event=args.raw_event,
        command=command,
        runtime_provider=args.runtime_provider,
        runtime_agent_id=args.runtime_agent_id,
        timeout=args.timeout,
        sign=args.sign,
        signature_key_env=args.signature_key_env,
        signature_key_id=args.signature_key_id,
    )
    return run_cli_subagent(cli_args)


def command_doctor(args: argparse.Namespace) -> int:
    if args.claude_command:
        command = shlex.split(args.claude_command) + ["--help"]
    else:
        command = [args.claude_bin, "--help"]
    result = subprocess.run(command, text=True, capture_output=True, check=False, env=os.environ.copy())
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        print(output.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    required = ["--print", "--output-format", "--no-session-persistence"]
    missing = [flag for flag in required if flag not in output]
    if missing:
        raise SystemExit("Claude command help is missing expected flag(s): " + ", ".join(missing))
    print("Claude Code CLI looks compatible with non-interactive subagent adapter.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a PWA subagent role through Claude Code CLI")
    sub = parser.add_subparsers(dest="command_name")

    run = sub.add_parser("run", help="Run Claude Code and write PWA host artifacts")
    run.add_argument("--role", required=True)
    run.add_argument("--task", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--raw-event", required=True)
    run.add_argument("--claude-bin", default="claude")
    run.add_argument(
        "--claude-command",
        default="",
        help="Override the full model CLI command. The generated prompt is passed on stdin.",
    )
    run.add_argument("--model", default="sonnet")
    run.add_argument("--permission-mode", default="dontAsk")
    run.add_argument("--tools", default="")
    run.add_argument("--bare", action="store_true")
    run.add_argument("--append-system-prompt", default="")
    run.add_argument("--max-budget-usd", default="")
    run.add_argument("--runtime-provider", default="claude-code-cli")
    run.add_argument("--runtime-agent-id", default="")
    run.add_argument("--timeout", type=int, default=900)
    run.add_argument("--sign", action="store_true")
    run.add_argument("--signature-key-env", default="PWA_RUNTIME_SIGNING_KEY")
    run.add_argument("--signature-key-id", default="claude-code-cli")
    run.set_defaults(func=command_run)

    doctor = sub.add_parser("doctor", help="Check whether Claude Code CLI exposes required non-interactive flags")
    doctor.add_argument("--claude-bin", default="claude")
    doctor.add_argument("--claude-command", default="")
    doctor.set_defaults(func=command_doctor)

    parser.set_defaults(func=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
