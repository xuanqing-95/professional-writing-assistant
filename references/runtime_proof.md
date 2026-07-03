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

This proof is stronger than a bare `runtime_agent_id` because it binds the raw runtime event to the task and output hashes. It is still not a cryptographic signature.

For high-assurance environments, the host runtime should sign the proof or write it to an append-only external event store.
