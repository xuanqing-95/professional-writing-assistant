#!/usr/bin/env python3
"""Convert a Codex subagent completion export into a runner runtime event."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from workflow_runtime import (
    RUNTIME_AGENT_ID_RE,
    artifact_record,
    read_agent_frontmatter,
    read_json,
    runtime_raw_event_relpath,
    utc_now,
    write_json,
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def extract_completed_text(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, dict) and isinstance(status.get("completed"), str):
        return status["completed"]
    for key in ["completed", "final_message", "output", "message"]:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    raise SystemExit("raw event does not contain completed output text")


def extract_runtime_agent_id(payload: dict[str, Any]) -> str:
    for key in ["agent_path", "runtime_agent_id", "agent_id", "id"]:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise SystemExit("raw event does not contain an agent id")


def assert_output_contains_completion(output_path: Path, completed_text: str) -> None:
    output_body = strip_frontmatter(output_path.read_text(encoding="utf-8"))
    normalized_output = normalize_text(output_body)
    normalized_completed = normalize_text(completed_text)
    if not normalized_completed:
        raise SystemExit("raw event completed output is empty")
    if normalized_completed not in normalized_output:
        raise SystemExit(
            "agent output file must contain the raw subagent completed text; paste subagent output verbatim"
        )


def command_adapt(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    role = args.role
    raw_source = Path(args.raw_event).resolve()
    if not raw_source.exists():
        raise SystemExit(f"raw event not found: {raw_source}")
    output_path = root / "agent_outputs" / f"{role}.md"
    if not output_path.exists():
        raise SystemExit(f"agent output not found: {output_path}")
    frontmatter = read_agent_frontmatter(output_path)
    if frontmatter.get("agent") != role:
        raise SystemExit(f"agent output frontmatter agent mismatch for {role}")
    if frontmatter.get("mode") != "subagent":
        raise SystemExit(f"agent output for {role} must use mode: subagent")

    raw_payload = read_json(raw_source)
    runtime_agent_id = args.runtime_agent_id or extract_runtime_agent_id(raw_payload)
    if not RUNTIME_AGENT_ID_RE.match(runtime_agent_id):
        raise SystemExit("runtime agent id must be UUID-like")
    completed_text = extract_completed_text(raw_payload)
    assert_output_contains_completion(output_path, completed_text)

    raw_target = root / runtime_raw_event_relpath(role)
    write_json(raw_target, raw_payload)
    raw_artifact = artifact_record(raw_target, root)
    event_payload = {
        "schema_version": 1,
        "event_type": "codex.subagent.completed",
        "runtime_provider": args.runtime_provider,
        "runtime_agent_id": runtime_agent_id,
        "role": role,
        "completed_at": args.completed_at or utc_now(),
        "raw_event_artifact": raw_artifact,
        "output_artifact": artifact_record(output_path, root),
    }

    out_path = Path(args.out).resolve() if args.out else root / "runtime_event_imports" / f"{role}.json"
    write_json(out_path, event_payload)
    print(out_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adapt Codex subagent raw event for workflow runner")
    parser.add_argument("--workflow-dir", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--raw-event", required=True)
    parser.add_argument("--runtime-agent-id", default="")
    parser.add_argument("--runtime-provider", default="codex")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--out", default="")
    return parser


def main() -> int:
    parser = build_parser()
    return command_adapt(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
