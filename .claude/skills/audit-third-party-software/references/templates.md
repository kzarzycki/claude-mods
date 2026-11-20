# Vendor issue and hardening templates

## Vendor issue

For findings worth reporting upstream: factual, specific, non-accusatory, 200–300 words.

The title states the claim and what contradicts it: "README says 'runs entirely
locally' — the runtime calls `api.voicetext.site` on every launch", not "Security
concerns about this project".

```markdown
<one-line disclosure when the analysis was AI-assisted, e.g. "_Static analysis was done with <tool> before installing; I reviewed and endorse the findings below. Happy to share the full audit output._">

I ran static analysis on <artifact> before installing (<hash or version>).

<Concrete finding: endpoints, file:line, quoted strings.>

<Quote of the contradicting README or marketing claim.>

That's not accurate — <why, in one sentence>.

## What I'd like to ask

- **<Top ask>.** <Why it matters, one sentence.>
- **<Each further ask only if distinct>.**

<One closing line inviting correction if there is documentation you missed.>
```

Leave out preamble ("in good faith", "in the spirit of"), asks that restate each other,
an environment or metadata footer, headings nested past two levels, and hedging.

## Local hardening note

When the user runs the software anyway with patches, record them so the patches survive
upstream updates:

````markdown
# Local hardening — <project>

**Branch:** `local/harden` · **Base commit:** <sha> · **Date:** YYYY-MM-DD

## Changes

- <path> — <one-line change>

## Why

<The threat mitigated, citing AUDIT_FINDINGS.md.>

## Verification

<Exact commands proving the mitigation, e.g. curl with different Origin headers.>

## Rebase

```bash
git checkout main && git pull
git checkout local/harden && git rebase main
```
````
