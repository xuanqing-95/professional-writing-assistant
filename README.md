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

```bash
python3 scripts/run_article_workflow.py \
  --source path/to/source.md \
  --out path/to/workflow-dir \
  --mode rewrite \
  --platform wechat
```

Then complete the generated workflow files and run:

```bash
python3 scripts/check_workflow_output.py path/to/workflow-dir
```

Only publish or share the final article after the checker passes.

## Design Principles

- Preserve source meaning before improving the article.
- Treat author voice as a constraint, not decoration.
- Prefer light edits when the user wants to keep the original meaning closely.
- Use tables sparingly in public articles.
- Keep internal workflow notes out of the publish-ready body.

