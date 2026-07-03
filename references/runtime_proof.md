# Runtime Proof

Use this reference when a real subagent/expert produced an `agent_outputs/<role>.md` file.

The host runtime, not the article writer, should provide the raw event data. The runner generates the proof from that event and the current workflow artifacts. The proof binds one expert role to:

- the runtime agent id,
- the exact agent task artifact,
- the exact agent output artifact,
- the raw runtime event artifact.

## Runtime Event File

Save one raw event file per subagent role:

```text
runtime_events/<role>.json
```

The event records what the host runtime says actually completed.

```json
{
  "schema_version": 1,
  "event_type": "codex.subagent.completed",
  "runtime_provider": "codex",
  "runtime_agent_id": "019f27cd-0000-7000-8000-000000000001",
  "role": "strategist",
  "completed_at": "2026-07-03T12:00:00Z",
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

The runner creates this file when recording a subagent output:

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
