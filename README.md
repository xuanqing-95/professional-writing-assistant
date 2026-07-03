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
- `scripts/check_workflow_output.py`: validates the workflow before delivery.
- `scripts/check_author_voice.py`: checks whether the rewrite preserves the author's voice.
- `scripts/check_article_readability.py`: checks whether the publish body reads like an article instead of a work note.

## Quick Start

Download the packaged Skill from the latest release:

https://github.com/xuanqing-95/professional-writing-assistant/releases/latest

Or run from the source checkout:

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

Use `--mode subagent --runtime-agent-id <agent-id>` when a real subagent produced the output.
Do not invent this id manually. If the runtime cannot provide a real UUID-like agent id, use `--mode simulated`.

Check and finalize:

```bash
python3 scripts/run_workflow.py check path/to/workflow-dir
python3 scripts/run_workflow.py finalize path/to/workflow-dir
```

Only publish or share the final article after finalize passes.

## Runner Evidence

The runner writes:

- `run_state.json`: current workflow state and recorded agent outputs.
- `logs/run_log.jsonl`: append-only event log with hash chaining.
- `gate_result.json`: final checker result after `check` or `finalize`.

`mode: subagent` in an agent output is not trusted by itself. The checker requires matching runner evidence and a runtime agent id.

Current trust levels:

- `simulated`: recorded and reproducible, but not independent expert execution.
- `subagent`: requires matching runner evidence and a UUID-like runtime agent id.
- The local runner is not a cryptographic audit service. It catches missing records, mode mismatches, hash changes, source changes, and simple fake ids; strong proof still requires the host runtime to write signed or otherwise verifiable subagent execution records.

## Design Principles

- Preserve source meaning before improving the article.
- Treat author voice as a constraint, not decoration.
- Prefer light edits when the user wants to keep the original meaning closely.
- Use tables sparingly in public articles.
- Keep internal workflow notes out of the publish-ready body.
