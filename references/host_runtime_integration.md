# Host Runtime Integration

Use this reference when a host environment can launch real subagents and you want the Skill to record them without manual adapter/record steps.

The Skill cannot create host-level subagent capability by itself. A host runtime must provide a command that actually runs a separate expert and writes:

- `agent_outputs/<role>.md`
- a raw runtime event JSON

Then `scripts/run_host_subagents.py` calls the host command for each role, adapts the raw event, records the output, and optionally finalizes with signed-event strict mode.

## Host Command Contract

The host command receives paths through command placeholders and environment variables.

Supported placeholders:

```text
{workflow_dir}
{role}
{task}
{output}
{raw_event}
```

The supervisor also sets these environment variables:

```text
PWA_WORKFLOW_DIR
PWA_ROLE
PWA_AGENT_TASK
PWA_AGENT_OUTPUT
PWA_RAW_EVENT
PWA_RUNTIME_PROVIDER
PWA_RUNTIME_SIGNING_KEY
```

The host command must:

1. Read `PWA_AGENT_TASK` or the `{task}` path.
2. Spawn a real isolated subagent/expert for `PWA_ROLE`.
3. Write the expert's raw answer into `PWA_AGENT_OUTPUT` with frontmatter:

   ```markdown
   ---
   agent: strategist
   mode: subagent
   ---
   ```

4. Write a raw runtime event JSON to `PWA_RAW_EVENT`.
5. Include a UUID-like runtime id in `agent_path`, `runtime_agent_id`, `agent_id`, or `id`.
6. Include the raw completed text in `status.completed`, `completed`, `final_message`, `output`, or `message`.
7. For strict mode, include `runtime_signature`.

## Strict Signed Run

Use a host command that signs raw events:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_host_subagents.py <workflow-dir> \
    --command "<host-command> --role {role} --task '{task}' --output '{output}' --raw-event '{raw_event}'" \
    --runtime-provider codex \
    --require-signature \
    --finalize
```

If the host exposes a CLI that reads the task prompt from stdin and prints the expert answer to stdout, use `scripts/cli_subagent_command.py` as the host command adapter:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_host_subagents.py <workflow-dir> \
    --command "python3 scripts/cli_subagent_command.py --role {role} --task '{task}' --output '{output}' --raw-event '{raw_event}' --command '<model-cli-command>' --sign" \
    --runtime-provider cli-subagent \
    --require-signature \
    --finalize
```

The CLI adapter:

1. Reads the generated agent task file.
2. Sends a role-specific prompt to `<model-cli-command>` through stdin.
3. Captures stdout as the raw expert answer.
4. Writes `agent_outputs/<role>.md` with `mode: subagent`.
5. Writes a signed raw runtime event JSON for the supervisor to verify and record.

This adapter proves that a separate CLI process ran and produced stdout. Whether that CLI process is a truly isolated subagent depends on the command you provide.

## Claude Code CLI Adapter

This repository includes a ready adapter for Claude Code CLI:

```bash
python3 scripts/claude_code_subagent_command.py doctor
```

If the doctor passes, run all workflow experts through Claude Code CLI:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_host_subagents.py <workflow-dir> \
    --command "python3 scripts/claude_code_subagent_command.py run --role {role} --task '{task}' --output '{output}' --raw-event '{raw_event}' --sign --bare --model sonnet" \
    --runtime-provider claude-code-cli \
    --require-signature \
    --finalize
```

The adapter uses Claude Code's non-interactive print mode by default:

```text
claude -p --output-format text --no-session-persistence --permission-mode dontAsk --model sonnet
```

Use `--claude-command "<custom command>"` when your environment needs a different Claude-compatible command. The task prompt is passed through stdin.

With `--require-signature`, the supervisor:

1. Rejects unsigned raw events.
2. Runs `scripts/adapt_codex_subagent_event.py --require-signature`.
3. Runs `scripts/run_workflow.py record-agent --mode subagent`.
4. If `--finalize` is set, runs `scripts/run_workflow.py finalize --require-signed-runtime-events`.

## Trust Boundary

This makes the workflow harder to fake because the main writing agent no longer manually runs each adapter/record step.

It still depends on the host runtime to actually spawn isolated subagents and protect `PWA_RUNTIME_SIGNING_KEY`. For stronger audit, write the raw event or signature receipt to an external append-only event store.
