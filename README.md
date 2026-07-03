# Professional Writing Assistant Skill

专业个人经验文章写作助手。用于把粗糙想法、项目复盘、AI 工具实践、产品/设计/运营经验，改造成适合 Medium、微信公众号、newsletter、博客等平台发布的高质量文章。

## What It Does

This Skill turns personal experience into publishable articles while preserving:

- original author voice
- source meaning and factual boundaries
- image placement and captions
- article readability
- reusable reader value

It includes a file-backed workflow with source claim mapping, author voice extraction, multi-role review, fidelity review, and validation scripts.

## Recommended Use

Use this Skill when you want to:

- rewrite a rough draft into a publishable article
- turn a project recap into a public essay
- preserve the original author's style while improving structure
- keep source images in the right positions
- avoid over-polishing into generic AI writing
- check whether a rewrite changed the original meaning

## Key Workflow Files

- `SKILL.md`: Skill entrypoint and operating rules.
- `references/`: strategy, structure, platform adaptation, source fidelity, author voice, and quality references.
- `agents/`: role prompts for strategy, interviewing, writing, narrative, fidelity, credibility, and review.
- `scripts/run_article_workflow.py`: creates the workflow packet.
- `scripts/run_workflow.py`: prepares, records, checks, and finalizes auditable workflow runs.
- `scripts/pwa_demo.py`: runs a complete local simulated quickstart workflow.
- `scripts/run_host_subagents.py`: runs host-provided subagent commands and records signed evidence.
- `scripts/cli_subagent_command.py`: wraps a stdin/stdout model CLI as a host subagent command.
- `scripts/claude_code_subagent_command.py`: wraps Claude Code CLI as a signed host subagent command.
- `scripts/check_workflow_output.py`: validates the workflow before delivery.
- `scripts/check_author_voice.py`: checks whether the rewrite preserves the author's voice.
- `scripts/check_source_fidelity.py`: checks high-risk source-meaning drift.
- `scripts/check_article_readability.py`: checks whether the publish body reads like an article instead of a work note.

## Quick Start

Download the packaged Skill from the latest release:

https://github.com/xuanqing-95/professional-writing-assistant/releases/latest

### Path 1: 3-minute local demo

Use this first if you only want to verify the workflow works. It does not require Claude, subagents, or signing.

```bash
python3 scripts/pwa_demo.py
```

The demo prepares a workflow, fills a small simulated article packet, records all expert outputs as `mode: simulated`, runs the gates, and prints the workflow path.

### Path 2: Agent-assisted article workflow

Use this when an AI agent will fill the generated workflow files and write the final article.

```bash
python3 scripts/run_workflow.py prepare \
  --source path/to/source.md \
  --out path/to/workflow-dir \
  --mode rewrite \
  --platform wechat
```

Then complete the generated workflow files. After writing each agent output, record it:

```bash
python3 scripts/run_workflow.py record-agent path/to/workflow-dir \
  --role fidelity_reviewer \
  --mode simulated
```

### Path 3: strict real-subagent workflow

Use this only when your host runtime can launch real subagents and provide raw runtime events. For signed publication runs, the host must also protect `PWA_RUNTIME_SIGNING_KEY`.

When a real subagent produced the output, first adapt the raw Codex subagent event:

```bash
python3 scripts/adapt_codex_subagent_event.py \
  --workflow-dir path/to/workflow-dir \
  --role fidelity_reviewer \
  --raw-event path/to/raw-subagent-event.json \
  --runtime-agent-id <agent-id>
```

For a high-assurance host that signs raw subagent events, require signature verification during adaptation:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/adapt_codex_subagent_event.py \
    --workflow-dir path/to/workflow-dir \
    --role fidelity_reviewer \
    --raw-event path/to/raw-subagent-event.json \
    --runtime-agent-id <agent-id> \
    --require-signature
```

Then record the subagent output with the generated event path printed by the adapter. Do not invent this id or event manually. If the runtime cannot provide a real UUID-like agent id and raw event, use `--mode simulated`.

```bash
python3 scripts/run_workflow.py record-agent path/to/workflow-dir \
  --role fidelity_reviewer \
  --mode subagent \
  --runtime-agent-id <agent-id> \
  --runtime-event <generated-event.json>
```

If your host runtime can launch real subagents through a command, use the supervisor to avoid manual adapter/record steps:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_host_subagents.py path/to/workflow-dir \
    --command "<host-command> --role {role} --task '{task}' --output '{output}' --raw-event '{raw_event}'" \
    --runtime-provider codex \
    --require-signature \
    --finalize
```

See `references/host_runtime_integration.md` for the host command contract.

For CLI-based runtimes that read stdin and return Markdown on stdout, wrap the CLI with:

```bash
python3 scripts/cli_subagent_command.py \
  --role {role} \
  --task '{task}' \
  --output '{output}' \
  --raw-event '{raw_event}' \
  --command '<model-cli-command>' \
  --sign
```

For Claude Code CLI specifically:

```bash
python3 scripts/claude_code_subagent_command.py doctor

PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_host_subagents.py path/to/workflow-dir \
    --command "python3 scripts/claude_code_subagent_command.py run --role {role} --task '{task}' --output '{output}' --raw-event '{raw_event}' --sign" \
    --runtime-provider claude-code-cli \
    --require-signature \
    --finalize
```

Check and finalize:

```bash
python3 scripts/run_workflow.py check path/to/workflow-dir
python3 scripts/run_workflow.py finalize path/to/workflow-dir
```

For strict publication runs where every expert must be a signed real subagent:

```bash
PWA_RUNTIME_SIGNING_KEY=<host-signing-key> \
  python3 scripts/run_workflow.py finalize path/to/workflow-dir \
    --require-signed-runtime-events
```

Only publish or share the final article after finalize passes.

## Runner Evidence

The runner writes:

- `run_state.json`: current workflow state and recorded agent outputs.
- `logs/run_log.jsonl`: append-only event log with hash chaining.
- `runtime_raw_events/<role>.json`: archived raw host-runtime event for a completed subagent role.
- `runtime_events/<role>.json`: adapted runner runtime event.
- `runtime_proofs/<role>.json`: runner-generated proof artifact that binds a subagent role to the runtime id, task hash, output hash, and raw event hash.
- `runtime_host_events/<role>.json`: host-supervisor input event before the adapter archives it.
- `gate_result.json`: final checker result after `check` or `finalize`.

`mode: subagent` in an agent output is not trusted by itself. The checker requires matching runner evidence, a runtime agent id, a raw runtime event artifact, and a runtime proof artifact.

Current trust levels:

- `simulated`: recorded and reproducible, but not independent expert execution.
- `subagent`: requires matching runner evidence, a UUID-like runtime agent id, an archived raw runtime event, an adapted runtime event, and a runner-generated proof file bound to the task/output/event hashes.
- `signed subagent`: requires the host raw event to include a valid `runtime_signature` and requires `finalize --require-signed-runtime-events`.
- The local runner catches missing records, mode mismatches, hash changes, source changes, bare UUID claims, detached proof claims, event tampering, proof tampering, and unsigned events in strict mode. Strong proof still requires the host runtime to automatically write and sign subagent execution records.

## Design Principles

- Preserve source meaning before improving the article.
- Treat author voice as a constraint, not decoration.
- Prefer light edits when the user wants to keep the original meaning closely.
- Use tables sparingly in public articles.
- Keep internal workflow notes out of the publish-ready body.
