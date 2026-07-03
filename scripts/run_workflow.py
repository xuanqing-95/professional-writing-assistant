#!/usr/bin/env python3
"""Auditable runner for the Professional Writing Assistant workflow."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from run_article_workflow import REQUIRED_FILES, build_packet
from workflow_runtime import (
    AGENT_ROLES,
    GATE_RESULT,
    RUN_LOG,
    RUN_STATE,
    RUNTIME_AGENT_ID_RE,
    VALID_AGENT_MODES,
    append_event,
    artifact_record,
    collect_artifacts,
    ensure_inside,
    load_state,
    new_run_id,
    read_json,
    read_agent_frontmatter,
    runtime_event_relpath,
    runtime_proof_relpath,
    save_state,
    utc_now,
    validate_runtime_event_payload,
    validate_runtime_proof_payload,
    write_json,
)


DEFAULT_ARTIFACT_PATTERNS = [
    "00_*.md",
    "00_manifest.json",
    "01_*.md",
    "02_*.md",
    "03_*.md",
    "04*.md",
    "05_*.md",
    "06_*.md",
    "07*.md",
    "08_*.md",
    "09_*.md",
    "10_*.md",
    "agent_tasks/*.md",
    "agent_outputs/*.md",
    "runtime_events/*.json",
    "runtime_proofs/*.json",
    "final_publish_article.md",
]


def command_prepare(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    out_dir = Path(args.out).resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")
    if source.is_dir():
        raise SystemExit(f"source must be a file: {source}")
    if out_dir == source.parent:
        raise SystemExit("--out must be a dedicated workflow directory, not the source directory")
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"workflow dir is not empty: {out_dir}. Use --force to reuse it.")

    build_packet(source, out_dir, args.mode, args.platform)
    run_id = new_run_id()
    source_artifact = artifact_record(out_dir / "00_source.md", out_dir)
    initial_artifacts = collect_artifacts(out_dir, DEFAULT_ARTIFACT_PATTERNS)
    state = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "prepared",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "runner": "scripts/run_workflow.py",
        "mode": args.mode,
        "platform": args.platform,
        "source": str(source),
        "workflow_dir": str(out_dir),
        "source_artifact": source_artifact,
        "agent_roles": AGENT_ROLES,
        "agent_outputs": {},
        "finalized": False,
        "gate_result": None,
    }
    save_state(out_dir, state)
    append_event(
        out_dir,
        "run_prepared",
        {
            "run_id": run_id,
            "mode": args.mode,
            "platform": args.platform,
            "source": str(source),
            "source_artifact": source_artifact,
            "artifact_count": len(initial_artifacts),
        },
    )
    for record in initial_artifacts:
        append_event(out_dir, "artifact_recorded", {"run_id": run_id, "artifact": record})
    print(f"Prepared workflow: {out_dir}")
    print(f"run_id: {run_id}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    state = load_state(root)
    print(f"run_id: {state.get('run_id')}")
    print(f"status: {state.get('status')}")
    print(f"workflow_dir: {root}")
    outputs = state.get("agent_outputs", {})
    print(f"agent_outputs_recorded: {len(outputs)}/{len(AGENT_ROLES)}")
    missing = [role for role in AGENT_ROLES if role not in outputs]
    if missing:
        print("missing_agent_records: " + ", ".join(missing))
    gate = state.get("gate_result")
    if gate:
        print(f"gate: {gate.get('status')} exit={gate.get('exit_code')}")
    return 0


def command_record_agent(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    state = load_state(root)
    role = args.role
    if role not in AGENT_ROLES:
        raise SystemExit(f"unknown role: {role}")
    output_path = root / "agent_outputs" / f"{role}.md"
    task_path = root / "agent_tasks" / f"{role}.md"
    ensure_inside(output_path, root, "agent output")
    if not output_path.exists():
        raise SystemExit(f"agent output not found: {output_path}")
    if not task_path.exists():
        raise SystemExit(f"agent task not found: {task_path}")
    frontmatter = read_agent_frontmatter(output_path)
    declared_agent = frontmatter.get("agent")
    declared_mode = frontmatter.get("mode")
    if declared_agent != role:
        raise SystemExit(
            f"agent output frontmatter mismatch: expected agent={role}, got {declared_agent or '(missing)'}"
        )
    if declared_mode != args.mode:
        raise SystemExit(
            f"agent output mode mismatch: frontmatter={declared_mode or '(missing)'}, record-agent={args.mode}"
        )
    output_artifact = artifact_record(output_path, root)
    task_artifact = artifact_record(task_path, root)
    runtime_event_artifact = None
    runtime_proof_artifact = None
    if args.mode == "subagent":
        if not args.runtime_agent_id:
            raise SystemExit("subagent mode requires --runtime-agent-id from the runtime")
        if not RUNTIME_AGENT_ID_RE.match(args.runtime_agent_id):
            raise SystemExit("subagent --runtime-agent-id must be a UUID-like runtime id")
        if not args.runtime_event:
            raise SystemExit("subagent mode requires --runtime-event from the host runtime")
        if not args.runtime_proof:
            raise SystemExit("subagent mode requires --runtime-proof from the host runtime")
        event_source = Path(args.runtime_event).resolve()
        if not event_source.exists():
            raise SystemExit(f"runtime event not found: {event_source}")
        event_payload = read_json(event_source)
        event_errors = validate_runtime_event_payload(
            event_payload,
            role,
            args.runtime_agent_id,
            output_artifact,
        )
        if event_errors:
            raise SystemExit("invalid runtime event:\n- " + "\n- ".join(event_errors))
        event_target = root / runtime_event_relpath(role)
        write_json(event_target, event_payload)
        runtime_event_artifact = artifact_record(event_target, root)

        proof_source = Path(args.runtime_proof).resolve()
        if not proof_source.exists():
            raise SystemExit(f"runtime proof not found: {proof_source}")
        proof_payload = read_json(proof_source)
        proof_errors = validate_runtime_proof_payload(
            proof_payload,
            role,
            args.runtime_agent_id,
            task_artifact,
            output_artifact,
            runtime_event_artifact,
        )
        if proof_errors:
            raise SystemExit("invalid runtime proof:\n- " + "\n- ".join(proof_errors))
        proof_target = root / runtime_proof_relpath(role)
        write_json(proof_target, proof_payload)
        runtime_proof_artifact = artifact_record(proof_target, root)

    record = {
        "role": role,
        "mode": args.mode,
        "runtime_agent_id": args.runtime_agent_id or "",
        "runtime_event_artifact": runtime_event_artifact,
        "runtime_proof_artifact": runtime_proof_artifact,
        "task_artifact": task_artifact,
        "output_artifact": output_artifact,
        "recorded_at": utc_now(),
    }
    state.setdefault("agent_outputs", {})[role] = record
    save_state(root, state)
    append_event(
        root,
        "agent_output_recorded",
        {
            "run_id": state.get("run_id"),
            **record,
        },
    )
    print(f"Recorded {role}: {args.mode} {output_artifact['sha256']}")
    return 0


def run_checker(root: Path, require_runner: bool) -> subprocess.CompletedProcess[str]:
    checker = Path(__file__).with_name("check_workflow_output.py")
    command = [sys.executable, str(checker), str(root)]
    if require_runner:
        command.append("--require-runner")
    return subprocess.run(command, text=True, capture_output=True, check=False)


def command_check(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    state = load_state(root)
    result = run_checker(root, require_runner=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    gate = {
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "checked_at": utc_now(),
    }
    state["gate_result"] = gate
    state["status"] = "checked_pass" if result.returncode == 0 else "checked_fail"
    save_state(root, state)
    write_json(root / GATE_RESULT, gate)
    append_event(
        root,
        "gate_checked",
        {
            "run_id": state.get("run_id"),
            "gate": gate,
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        },
    )
    return result.returncode


def command_finalize(args: argparse.Namespace) -> int:
    root = Path(args.workflow_dir).resolve()
    state = load_state(root)
    result = run_checker(root, require_runner=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        state["status"] = "finalize_blocked"
        state["gate_result"] = {
            "status": "fail",
            "exit_code": result.returncode,
            "checked_at": utc_now(),
        }
        save_state(root, state)
        append_event(root, "finalize_blocked", {"run_id": state.get("run_id"), "exit_code": result.returncode})
        return result.returncode

    final_path = root / "final_publish_article.md"
    final_artifact = artifact_record(final_path, root)
    gate = {
        "status": "pass",
        "exit_code": 0,
        "checked_at": utc_now(),
        "final_artifact": final_artifact,
    }
    state["status"] = "finalized"
    state["finalized"] = True
    state["gate_result"] = gate
    save_state(root, state)
    write_json(root / GATE_RESULT, gate)
    append_event(
        root,
        "run_finalized",
        {
            "run_id": state.get("run_id"),
            "gate": gate,
            "final_artifact": final_artifact,
        },
    )
    print(f"Finalized workflow: {root}")
    print(f"final_sha256: {final_artifact['sha256']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run auditable article workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Create workflow packet and run state")
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--out", required=True)
    prepare.add_argument("--mode", default="rewrite", choices=["diagnostic", "planning", "rewrite", "full-package"])
    prepare.add_argument("--platform", default="unspecified")
    prepare.add_argument("--force", action="store_true")
    prepare.set_defaults(func=command_prepare)

    status = sub.add_parser("status", help="Show run status")
    status.add_argument("workflow_dir")
    status.set_defaults(func=command_status)

    record = sub.add_parser("record-agent", help="Record agent output provenance")
    record.add_argument("workflow_dir")
    record.add_argument("--role", required=True, choices=AGENT_ROLES)
    record.add_argument("--mode", required=True, choices=VALID_AGENT_MODES)
    record.add_argument("--runtime-agent-id", default="")
    record.add_argument("--runtime-event", default="", help="Raw JSON event emitted by the host runtime for subagent mode")
    record.add_argument("--runtime-proof", default="", help="JSON proof emitted by the host runtime for subagent mode")
    record.set_defaults(func=command_record_agent)

    check = sub.add_parser("check", help="Run checker with runner evidence required")
    check.add_argument("workflow_dir")
    check.set_defaults(func=command_check)

    finalize = sub.add_parser("finalize", help="Finalize only after all gates pass")
    finalize.add_argument("workflow_dir")
    finalize.set_defaults(func=command_finalize)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
