#!/usr/bin/env python3
"""Validate that an article workflow packet was actually completed."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"<!-- REQUIRED:.*?-->", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check completed article workflow packet")
    parser.add_argument("workflow_dir", help="Workflow directory created by run_article_workflow.py")
    args = parser.parse_args()

    root = Path(args.workflow_dir).resolve()
    manifest_path = root / "00_manifest.json"
    if not manifest_path.exists():
        print(f"FAIL missing manifest: {manifest_path}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_files = manifest.get("required_files", [])
    errors: list[str] = []

    for rel in required_files:
        path = root / rel
        if not path.exists():
            errors.append(f"missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if rel.endswith(".md") and PLACEHOLDER_RE.search(text):
            errors.append(f"unfilled placeholders in {rel}")
        if rel.startswith("agent_outputs/") and rel.endswith(".md"):
            match = FRONTMATTER_RE.match(text)
            if not match:
                errors.append(f"missing frontmatter in {rel}")
            else:
                frontmatter = match.group(1)
                if "mode: subagent" not in frontmatter and "mode: simulated" not in frontmatter:
                    errors.append(f"missing mode provenance in {rel}")
                if "mode: simulated" in frontmatter:
                    print(f"WARN simulated expert output: {rel}")

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
