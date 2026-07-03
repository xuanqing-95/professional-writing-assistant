#!/usr/bin/env python3
"""Validate that an article workflow packet was actually completed."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from workflow_runtime import (
    RUNTIME_AGENT_ID_RE,
    VALID_AGENT_MODES,
    iter_log_events,
    read_agent_frontmatter,
    read_json,
    runtime_proof_relpath,
    sha256_file,
    validate_runtime_proof_payload,
    validate_log_chain,
)


PLACEHOLDER_RE = re.compile(r"<!-- REQUIRED:.*?-->", re.DOTALL)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
INTERNAL_PUBLISH_SECTIONS = [
    "## Title Options",
    "## Final Article",
    "## Image Placement Notes",
    "## Screenshot-Worthy Lines",
    "## Reusable Reader Component",
    "## Credibility Notes",
    "# 09 Final Article",
]

FIDELITY_PASS_RE = re.compile(r"\bpass\b|通过|无实质语义漂移", re.IGNORECASE)
FIDELITY_BLOCK_RE = re.compile(r"needs revision|blocked|不通过|需要修订|待作者确认", re.IGNORECASE)


def validate_runner_evidence(root: Path, agent_modes: dict[str, str]) -> list[str]:
    errors: list[str] = []
    state_path = root / "run_state.json"
    log_path = root / "logs" / "run_log.jsonl"

    if not state_path.exists():
        return ["missing runner state: run_state.json"]
    if not log_path.exists():
        return ["missing runner log: logs/run_log.jsonl"]

    state = read_json(state_path)
    events = iter_log_events(root)
    errors.extend(validate_log_chain(root))

    if not any(event.get("event_type") == "run_prepared" for event in events):
        errors.append("runner log missing run_prepared event")

    source_record = state.get("source_artifact") or {}
    source_path = root / source_record.get("path", "")
    if source_record and source_path.exists():
        if sha256_file(source_path) != source_record.get("sha256"):
            errors.append("00_source.md hash does not match run_state source_artifact")

    recorded_outputs = state.get("agent_outputs") or {}
    output_events = [
        event for event in events if event.get("event_type") == "agent_output_recorded"
    ]
    for role, declared_mode in agent_modes.items():
        output_path = root / "agent_outputs" / f"{role}.md"
        output_hash = sha256_file(output_path)
        record = recorded_outputs.get(role)
        if not record:
            errors.append(f"runner has no recorded agent output for {role}")
            continue
        if record.get("mode") != declared_mode:
            errors.append(
                f"agent output mode mismatch for {role}: frontmatter={declared_mode}, runner={record.get('mode')}"
            )
        if record.get("output_artifact", {}).get("sha256") != output_hash:
            errors.append(f"agent output hash mismatch for {role}")
        matching_events = [
            event
            for event in output_events
            if event.get("role") == role
            and event.get("mode") == declared_mode
            and event.get("output_artifact", {}).get("sha256") == output_hash
        ]
        if not matching_events:
            errors.append(f"runner log missing matching agent_output_recorded event for {role}")
        if declared_mode == "subagent" and not record.get("runtime_agent_id"):
            errors.append(f"subagent output for {role} has no runtime_agent_id")
        if declared_mode == "subagent" and record.get("runtime_agent_id") and not RUNTIME_AGENT_ID_RE.match(
            record.get("runtime_agent_id", "")
        ):
            errors.append(f"subagent output for {role} has invalid runtime_agent_id format")
        if declared_mode == "subagent":
            proof_record = record.get("runtime_proof_artifact") or {}
            if not proof_record:
                errors.append(f"subagent output for {role} has no runtime proof artifact")
            else:
                expected_proof_path = runtime_proof_relpath(role)
                if proof_record.get("path") != expected_proof_path:
                    errors.append(f"subagent runtime proof path mismatch for {role}")
                proof_path = root / proof_record.get("path", "")
                if not proof_path.exists():
                    errors.append(f"subagent runtime proof file missing for {role}")
                else:
                    if sha256_file(proof_path) != proof_record.get("sha256"):
                        errors.append(f"subagent runtime proof hash mismatch for {role}")
                    proof_payload = read_json(proof_path)
                    errors.extend(
                        validate_runtime_proof_payload(
                            proof_payload,
                            role,
                            record.get("runtime_agent_id", ""),
                            record.get("task_artifact", {}),
                            record.get("output_artifact", {}),
                        )
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check completed article workflow packet")
    parser.add_argument("workflow_dir", help="Workflow directory created by run_article_workflow.py")
    parser.add_argument(
        "--require-runner",
        action="store_true",
        help="Require run_state.json and logs/run_log.jsonl provenance evidence",
    )
    args = parser.parse_args()

    root = Path(args.workflow_dir).resolve()
    manifest_path = root / "00_manifest.json"
    if not manifest_path.exists():
        print(f"FAIL missing manifest: {manifest_path}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_files = manifest.get("required_files", [])
    errors: list[str] = []
    agent_modes: dict[str, str] = {}

    for rel in required_files:
        path = root / rel
        if not path.exists():
            errors.append(f"missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if rel.endswith(".md") and PLACEHOLDER_RE.search(text):
            errors.append(f"unfilled placeholders in {rel}")
        if rel.startswith("agent_outputs/") and rel.endswith(".md"):
            frontmatter = read_agent_frontmatter(path)
            if not frontmatter:
                errors.append(f"missing frontmatter in {rel}")
            else:
                expected_agent = Path(rel).stem
                declared_agent = frontmatter.get("agent")
                if declared_agent != expected_agent:
                    errors.append(
                        f"agent frontmatter mismatch in {rel}: expected {expected_agent}, got {declared_agent or '(missing)'}"
                    )
                mode = frontmatter.get("mode")
                if not mode:
                    errors.append(f"missing mode provenance in {rel}")
                elif mode not in VALID_AGENT_MODES:
                    errors.append(f"invalid mode provenance in {rel}: {mode}")
                else:
                    agent_modes[Path(rel).stem] = mode
                if mode == "simulated":
                    print(f"WARN simulated expert output: {rel}")

    if args.require_runner or (root / "run_state.json").exists():
        errors.extend(validate_runner_evidence(root, agent_modes))

    final_path = root / "09_final_article.md"
    source_image_count = int(manifest.get("image_count") or 0)
    if final_path.exists():
        final_text = final_path.read_text(encoding="utf-8")
        required_sections = [
            "## Title Options",
            "## Final Article",
            "## Image Placement Notes",
            "## Screenshot-Worthy Lines",
            "## Reusable Reader Component",
            "## Credibility Notes",
        ]
        for section in required_sections:
            if section not in final_text:
                errors.append(f"missing final section {section}")
        final_image_count = len(IMAGE_RE.findall(final_text))
        if source_image_count and final_image_count < source_image_count:
            errors.append(
                f"source has {source_image_count} images but final article has {final_image_count}"
            )

    fidelity_path = root / "07b_source_fidelity_review.md"
    if fidelity_path.exists():
        fidelity_text = fidelity_path.read_text(encoding="utf-8")
        if not FIDELITY_PASS_RE.search(fidelity_text):
            errors.append("source fidelity review does not contain a pass verdict")
        if FIDELITY_BLOCK_RE.search(fidelity_text):
            errors.append("source fidelity review contains unresolved revision/blocking language")

    publish_path = root / "final_publish_article.md"
    if publish_path.exists():
        publish_text = publish_path.read_text(encoding="utf-8")
        publish_image_count = len(IMAGE_RE.findall(publish_text))
        if source_image_count and publish_image_count < source_image_count:
            errors.append(
                f"source has {source_image_count} images but publish article has {publish_image_count}"
            )
        for section in INTERNAL_PUBLISH_SECTIONS:
            if section in publish_text:
                errors.append(f"internal workflow section leaked into publish article: {section}")

        voice_script = Path(__file__).with_name("check_author_voice.py")
        source_path = root / "00_source.md"
        if voice_script.exists() and source_path.exists():
            command = [
                sys.executable,
                str(voice_script),
                str(source_path),
                str(publish_path),
            ]
            profile_path = root / "04a_author_voice_profile.md"
            if profile_path.exists() and not PLACEHOLDER_RE.search(
                profile_path.read_text(encoding="utf-8")
            ):
                command.extend(["--profile", str(profile_path)])
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
            if result.returncode != 0:
                errors.append("author voice gate failed")

        readability_script = Path(__file__).with_name("check_article_readability.py")
        if readability_script.exists():
            result = subprocess.run(
                [
                    sys.executable,
                    str(readability_script),
                    str(publish_path),
                    "--source-image-count",
                    str(source_image_count),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
            if result.returncode != 0:
                errors.append("article readability gate failed")

    checklist_path = root / "10_workflow_checklist.md"
    if checklist_path.exists():
        checklist = checklist_path.read_text(encoding="utf-8")
        unchecked = [line for line in checklist.splitlines() if line.startswith("- [ ]")]
        if unchecked:
            errors.append(f"unchecked workflow checklist items: {len(unchecked)}")

    if errors:
        print("FAIL workflow incomplete")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS workflow complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
