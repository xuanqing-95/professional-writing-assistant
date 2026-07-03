# Author Voice DNA

Use this reference when rewriting a draft where the author wants the final article to keep their original flavor, writing characteristics, and personal voice.

Inspired by the `huashu-nuwa` expression-DNA method, but adapted for article rewriting: extract the author's operating voice from the source draft, then migrate it into a cleaner article without flattening it into generic platform prose.

## Core Distinction

Author voice is not surface imitation.

Do not merely copy a few口癖. Preserve the way the author:

- notices problems
- admits uncertainty
- moves from scene to judgment
- frames tools, products, users, and decisions
- hesitates, corrects, or sharpens a thought

The target is: **better organized, still recognizably written by the same person**.

## Extraction Dimensions

### 1. Stance

How does the author stand inside the article?

- first-person confessional
- product-manager observation
- beginner learning in public
- practitioner sharing a tested workflow
- designer noticing interaction details
- operator weighing cost, constraints, and delivery

### 2. Thinking Path

Track how the author usually reaches a point:

```text
具体场景 -> 当时误判 -> 试了一下 -> 发现问题不在那里 -> 新判断
```

Preserve this path when rewriting. Do not replace it with:

```text
背景介绍 -> 方法一二三 -> 总结升华
```

unless the source itself already works that way.

### 3. Sentence Rhythm

Look for:

- average paragraph length
- short spoken sentences
- rhetorical questions
- recurring transitions found in the source, such as hesitation, correction, discovery, or contrast markers
- cautious words such as "可能 / 我感觉 / 对我来说"
- places where the author makes a direct judgment

Use these as rhythm references, not as decorations. Do not force these examples into another author's article.

### 4. Judgment Cadence

Many personal-experience articles become generic because the rewrite removes the author's judgment rhythm.

Preserve source-derived patterns like:

```text
[author's original misconception pattern]
[author's discovery/correction pattern]
[author's final judgment pattern]
```

This is often more important than preserving exact words.

### 5. Vocabulary Field

Extract the author's real vocabulary:

- tool words
- product/design/operation words
- learning words
- cost and constraint words
- personal uncertainty words
- favorite verbs and nouns

Also record words the source never uses and should not suddenly appear. The vocabulary field must be extracted from the current source, not from examples, previous tests, or the Skill author's articles.

### 6. Anti-Voice List

Common voice killers:

- "本文将..."
- "下面我会..."
- "首先我们需要..."
- "值得注意的是..."
- "综上所述..."
- generic motivational endings
- polished but empty public-account voice
- fake results, fake certainty, or fake authority
- replacing "我" with neutral "我们/读者/大家" everywhere

## Three Validation Filters

Borrowed from expression-DNA extraction:

1. **Recurrence**: Does this trait appear more than once in the source?
2. **Generative Usefulness**: Can this trait guide rewriting a new section?
3. **Distinctiveness**: Does this separate the author from generic AI writing?

If a trait only passes one filter, mark it as weak. Do not overfit the whole rewrite to it.

## Source-Local Seed

For workflow packets, read `00_author_voice_seed.md` before completing `04a_author_voice_profile.md`.

The seed is generated from the current source and may include:

- first-person and collective voice counts;
- sentence and paragraph rhythm;
- source-derived stance, transition, caution, and certainty markers;
- repeated phrases from the current source.

Use the seed as evidence, not as a formula. A repeated phrase may be noise, and a rare phrase may be central if it captures the author's judgment. The editor must still decide what is voice, what is roughness, and what is accidental wording.

## Anti-Contamination Rule

Every voice claim must be traceable to one of:

- `00_source.md`
- `00_author_voice_seed.md`
- `agent_outputs/author_voice_analyst.md`

Never use style markers from:

- examples in this skill;
- eval prompts;
- previous users;
- the Skill author's own test articles;
- platform stereotypes.

## Workflow Requirements

For Rewrite and Full package tasks:

1. Complete `04a_author_voice_profile.md` before structure and narrative rewriting.
2. The profile must separate:
   - `Preserve`
   - `Clean Up`
   - `Do Not Introduce`
   - `Migration Rules`
3. `08_rewrite_plan.md` must include the voice migration plan.
4. `final_publish_article.md` must pass the author voice check.

## Good Rewrite Principle

The rewrite may improve:

- structure
- clarity
- pacing
- evidence order
- paragraph length
- image placement

The rewrite must not erase:

- first-person presence
- personal uncertainty
- the author's real thinking path
- domain-specific judgment
- concrete original scenes
- the author's recurring way of saying "I learned this the hard way"
