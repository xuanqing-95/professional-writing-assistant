# Runtime Proof

Use this reference when a real subagent/expert produced an `agent_outputs/<role>.md` file.

The host runtime, not the article writer, should provide the raw event data. Use `scripts/adapt_codex_subagent_event.py` to convert that raw event into a runner runtime event. The runner then generates the proof from the adapted event and current workflow artifacts. The proof binds one expert role to:

- the runtime agent id,
- the exact agent task artifact,
- the exact agent output artifact,
- the raw runtime event artifact.

## Raw Runtime Event File

The adapter archives one raw event file per subagent role:

```text
runtime_raw_events/<role>.json
```

For Codex subagent notifications, the raw event may look like:

```json
{
  "agent_path": "019f27cd-0000-7000-8000-000000000001",
  "status": {
    "completed": "# strategist\n\n..."
  }
}
```

The adapter requires the `agent_outputs/<role>.md` file to contain the raw completed text. Paste the subagent output verbatim after the frontmatter; summarize or edit later in workflow review files.

For high-assurance hosts, sign the raw event before handing it to the adapter. The signature field is named `runtime_signature` and signs the canonical JSON payload with that field excluded:

```json
{
  "agent_path": "019f27cd-0000-7000-8000-000000000001",
  "status": {
    "completed": "# strategist\n\n..."
  },
  "runtime_signature": {
    "alg": "hmac-sha256",
    "key_id": "host-key-2026-07",
    "value": "<hex hmac>"
  }
}
```

Use the adapter with signature verification:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/adapt_codex_subagent_event.py \
    --workflow-dir <workflow-dir> \
    --role <role> \
    --raw-event <raw-event.json> \
    --runtime-agent-id <agent-id> \
    --require-signature
```

If a host runtime can expose a reusable command that writes the agent output and raw event, use the supervisor instead of manually adapting each role. See `references/host_runtime_integration.md`.

## Adapted Runtime Event File

The adapter creates one runner event file per subagent role:

```text
runtime_events/<role>.json
```

The event records what the host runtime says actually completed and links back to the archived raw event.

```json
{
  "schema_version": 1,
  "event_type": "codex.subagent.completed",
  "runtime_provider": "codex",
  "runtime_agent_id": "019f27cd-0000-7000-8000-000000000001",
  "role": "strategist",
  "completed_at": "2026-07-03T12:00:00Z",
  "raw_event_artifact": {
    "path": "runtime_raw_events/strategist.json",
    "sha256": "...",
    "size": 999
  },
  "raw_event_signature_verified": true,
  "raw_event_signature_alg": "hmac-sha256",
  "raw_event_signature_key_id": "host-key-2026-07",
  "output_artifact": {
    "path": "agent_outputs/strategist.md",
    "sha256": "...",
    "size": 5678
  }
}
```

## Proof File

Save one proof file per subagent role:

```text
runtime_proofs/<role>.json
```

Use the adapter before recording:

```bash
python3 scripts/adapt_codex_subagent_event.py \
  --workflow-dir <workflow-dir> \
  --role <role> \
  --raw-event <raw-event.json> \
  --runtime-agent-id <agent-id>
```

Then pass the generated event path printed by the adapter:

```bash
python3 scripts/run_workflow.py record-agent <workflow-dir> \
  --role <role> \
  --mode subagent \
  --runtime-agent-id <agent-id> \
  --runtime-event <event.json>
```

For strict publication runs, finalize with signed runtime events required:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_workflow.py finalize <workflow-dir> \
    --require-signed-runtime-events
```

## Proof Schema

```json
{
  "schema_version": 1,
  "proof_type": "codex.subagent.runtime_proof",
  "proof_generated_by": "scripts/run_workflow.py",
  "runtime_provider": "codex",
  "runtime_agent_id": "019f27cd-0000-7000-8000-000000000001",
  "role": "strategist",
  "created_at": "2026-07-03T12:00:00Z",
  "runtime_event_artifact": {
    "path": "runtime_events/strategist.json",
    "sha256": "...",
    "size": 999
  },
  "task_artifact": {
    "path": "agent_tasks/strategist.md",
    "sha256": "...",
    "size": 1234
  },
  "output_artifact": {
    "path": "agent_outputs/strategist.md",
    "sha256": "...",
    "size": 5678
  }
}
```

## Trust Boundary

This proof is stronger than a bare `runtime_agent_id` because it binds the raw runtime event to the task and output hashes. In strict mode, the checker also re-verifies the archived raw event signature.

The remaining trust boundary is the host runtime. The Skill can verify a signed raw event, but it cannot force the host to spawn subagents or protect the signing key. For stronger audit, let the host write signed events to an append-only external event store.
