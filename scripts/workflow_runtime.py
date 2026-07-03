#!/usr/bin/env python3
"""Runtime helpers for auditable article workflow runs."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_STATE = "run_state.json"
RUN_LOG = "logs/run_log.jsonl"
GATE_RESULT = "gate_result.json"
RUNTIME_PROOFS_DIR = "runtime_proofs"
RUNTIME_EVENTS_DIR = "runtime_events"
AGENT_ROLES = [
    "strategist",
    "interviewer",
    "author_voice_analyst",
    "structure_editor",
    "narrative_editor",
    "fidelity_reviewer",
    "value_evaluator",
    "spread_evaluator",
    "credibility_risk",
]
VALID_AGENT_MODES = ["subagent", "simulated"]
RUNTIME_AGENT_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative_to_root(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def ensure_inside(path: Path, root: Path, label: str) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"{label} must be inside workflow dir: {path}")


def artifact_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": relative_to_root(path, root),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def iter_log_events(root: Path) -> list[dict[str, Any]]:
    log_path = root / RUN_LOG
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)
        event["_line"] = line_number
        events.append(event)
    return events


def _event_payload_for_hash(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key not in {"event_hash", "_line"}}


def compute_event_hash(event: dict[str, Any]) -> str:
    payload = json.dumps(_event_payload_for_hash(event), ensure_ascii=False, sort_keys=True)
    return sha256_text(payload)


def append_event(root: Path, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    log_path = root / RUN_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)

    previous_hash = ""
    previous_events = iter_log_events(root)
    if previous_events:
        previous_hash = previous_events[-1].get("event_hash", "")

    event: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "created_at": utc_now(),
        "prev_event_hash": previous_hash,
        **payload,
    }
    event["event_hash"] = compute_event_hash(event)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def validate_log_chain(root: Path) -> list[str]:
    errors: list[str] = []
    previous_hash = ""
    for event in iter_log_events(root):
        line = event.get("_line", "?")
        expected_prev = previous_hash
        if event.get("prev_event_hash", "") != expected_prev:
            errors.append(f"log line {line} has invalid prev_event_hash")
        recorded_hash = event.get("event_hash")
        computed_hash = compute_event_hash(event)
        if recorded_hash != computed_hash:
            errors.append(f"log line {line} has invalid event_hash")
        previous_hash = recorded_hash or ""
    return errors


def load_state(root: Path) -> dict[str, Any]:
    return read_json(root / RUN_STATE)


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    write_json(root / RUN_STATE, state)


def collect_artifacts(root: Path, patterns: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                records.append(artifact_record(path, root))
    return records


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    frontmatter: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("\"'")
    return frontmatter


def read_agent_frontmatter(path: Path) -> dict[str, str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def runtime_proof_relpath(role: str) -> str:
    return f"{RUNTIME_PROOFS_DIR}/{role}.json"


def runtime_event_relpath(role: str) -> str:
    return f"{RUNTIME_EVENTS_DIR}/{role}.json"


def validate_runtime_event_payload(
    payload: dict[str, Any],
    role: str,
    runtime_agent_id: str,
    output_artifact: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append(f"runtime event for {role} has invalid schema_version")
    if payload.get("event_type") != "codex.subagent.completed":
        errors.append(f"runtime event for {role} has invalid event_type")
    if payload.get("role") != role:
        errors.append(f"runtime event role mismatch for {role}")
    if payload.get("runtime_agent_id") != runtime_agent_id:
        errors.append(f"runtime event runtime_agent_id mismatch for {role}")
    if not payload.get("runtime_provider"):
        errors.append(f"runtime event for {role} missing runtime_provider")
    if not payload.get("completed_at"):
        errors.append(f"runtime event for {role} missing completed_at")

    event_output = payload.get("output_artifact") or {}
    for key in ["path", "sha256", "size"]:
        if event_output.get(key) != output_artifact.get(key):
            errors.append(f"runtime event output_artifact.{key} mismatch for {role}")
    return errors


def validate_runtime_proof_payload(
    payload: dict[str, Any],
    role: str,
    runtime_agent_id: str,
    task_artifact: dict[str, Any],
    output_artifact: dict[str, Any],
    runtime_event_artifact: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append(f"runtime proof for {role} has invalid schema_version")
    if payload.get("proof_type") != "codex.subagent.runtime_proof":
        errors.append(f"runtime proof for {role} has invalid proof_type")
    if payload.get("role") != role:
        errors.append(f"runtime proof role mismatch for {role}")
    if payload.get("runtime_agent_id") != runtime_agent_id:
        errors.append(f"runtime proof runtime_agent_id mismatch for {role}")
    if not payload.get("runtime_provider"):
        errors.append(f"runtime proof for {role} missing runtime_provider")
    if not payload.get("created_at"):
        errors.append(f"runtime proof for {role} missing created_at")
    if runtime_event_artifact is not None:
        proof_event = payload.get("runtime_event_artifact") or {}
        if not proof_event:
            errors.append(f"runtime proof for {role} missing runtime_event_artifact")
        for key in ["path", "sha256", "size"]:
            if proof_event.get(key) != runtime_event_artifact.get(key):
                errors.append(f"runtime proof runtime_event_artifact.{key} mismatch for {role}")

    proof_task = payload.get("task_artifact") or {}
    proof_output = payload.get("output_artifact") or {}
    for key in ["path", "sha256", "size"]:
        if proof_task.get(key) != task_artifact.get(key):
            errors.append(f"runtime proof task_artifact.{key} mismatch for {role}")
        if proof_output.get(key) != output_artifact.get(key):
            errors.append(f"runtime proof output_artifact.{key} mismatch for {role}")
    return errors
