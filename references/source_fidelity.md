# Source Fidelity Reference

## Goal

Improve the article without changing what the source means.

The rewrite may change:

- section order
- paragraph rhythm
- sentence clarity
- opening material
- repeated wording
- how reusable methods are packaged

The rewrite must not change:

- facts
- sequence
- causal logic
- author stance
- uncertainty level
- claims and boundaries
- what screenshots or evidence prove

## Change Budget

Use one of three levels before rewriting:

### Level 1: Light Edit

Use when the source is already close to publishable.

- Keep original structure mostly intact.
- Improve wording and flow.
- Do not add new interpretations.
- Keep all factual claims unchanged.

### Level 2: Structural Rewrite

Use by default for rough but meaningful drafts.

- Reorder sections for readability.
- Strengthen opening using material already in the source.
- Compress repetition.
- Add connective tissue, but mark unsupported additions for author verification.

### Level 3: Editorial Reconstruction

Use only when the user explicitly wants a major rewrite.

- Rebuild the article around a sharper thesis.
- Add framing and interpretation.
- Must maintain a visible list of additions requiring author verification.

## Source Claim Map

Before drafting, fill `00_source_claim_map.md`:

- non-negotiable facts
- core claims
- causal logic
- experience boundaries
- allowed changes
- forbidden changes

If the claim map is vague, do not write the final article yet.

## Fidelity Review Questions

Ask before finalizing:

1. Did the rewrite make the author sound more certain than the source?
2. Did it turn one project result into a general law?
3. Did it change why something worked or failed?
4. Did it remove an important limitation?
5. Did it add a new concept, metaphor, or conclusion that the author never implied?
6. Did it make the article more dramatic by changing sequence or motivation?
7. Would the source author read it and say, "This is cleaner, but still what I meant"?

## Required Verdict

`07b_source_fidelity_review.md` must end with one of:

- `pass`: no material meaning drift.
- `needs revision`: fix listed issues before publishing.
- `blocked`: author verification required.

Only `pass` can proceed to delivery.

## Script Gate

Run `scripts/check_source_fidelity.py 00_source.md final_publish_article.md` before delivery.
This script is a heuristic guard, not a full semantic judge. It catches high-risk drift such as:

- source numbers, dates, percentages, or time markers disappearing;
- cautious source language being rewritten as strong certainty;
- many repeated source terms disappearing from the article.

If the script fails, revise the article or record explicit author verification before delivery.
