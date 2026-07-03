#!/usr/bin/env python3
"""Test fixture that mimics a host subagent runtime."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path


def canonical_json_for_signature(payload: dict) -> str:
    unsigned_payload = {key: value for key, value in payload.items() if key != "runtime_signature"}
    return json.dumps(unsigned_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sign_payload(payload: dict, key: str) -> dict[str, str]:
    value = hmac.new(
        key.encode("utf-8"),
        canonical_json_for_signature(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "alg": "hmac-sha256",
        "key_id": "fake-host-test-key",
        "value": value,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fake host subagent for tests")
    parser.add_argument("--role", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-event", required=True)
    parser.add_argument("--sign", action="store_true")
    args = parser.parse_args()

    completed = f"# {args.role}\n\nfilled\n"
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"---\nagent: {args.role}\nmode: subagent\n---\n\n{completed}",
        encoding="utf-8",
    )

    raw_payload = {
        "agent_path": str(uuid.uuid4()),
        "status": {
            "completed": completed,
        },
    }
    if args.sign:
        key = os.environ.get("PWA_RUNTIME_SIGNING_KEY", "")
        if not key:
            raise SystemExit("PWA_RUNTIME_SIGNING_KEY is required when --sign is used")
        raw_payload["runtime_signature"] = sign_payload(raw_payload, key)

    raw_path = Path(args.raw_event)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
