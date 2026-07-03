# Runtime Proof

Use this reference when a real subagent/expert produced an `agent_outputs/<role>.md` file.

The host runtime, not the article writer, should provide the proof data. The proof binds one expert role to:

- the runtime agent id,
- the exact agent task artifact,
- the exact agent output artifact.

## Proof File

Save one JSON file per subagent role:

```text
runtime_proofs/<role>.json
```

The runner can copy an external proof into this location when recording:

```bash
python3 scripts/run_workflow.py record-agent <workflow-dir> \
  --role <role> \
  --mode subagent \
  --runtime-agent-id <agent-id> \
  --runtime-proof <proof.json>
```

## Schema

```json
{
  "schema_version": 1,
  "proof_type": "codex.subagent.runtime_proof",
  "runtime_provider": "codex",
  "runtime_agent_id": "019f27cd-0000-7000-8000-000000000001",
  "role": "strategist",
  "created_at": "2026-07-03T12:00:00Z",
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

This proof is stronger than a bare `runtime_agent_id` because it binds the runtime event to the task and output hashes. It is still not a cryptographic signature.

For high-assurance environments, the host runtime should sign the proof or write it to an append-only external event store.
