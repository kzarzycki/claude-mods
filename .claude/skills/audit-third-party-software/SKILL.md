---
name: audit-third-party-software
description: "Audit third-party code (repos, npm packages, binaries, plugins) for telemetry, exfiltration, supply-chain risk, and hostile defaults before install; verdict SAFE/CAUTION/UNSAFE with file:line evidence."
when_to_use: "User shows install intent for unfamiliar software — a GitHub URL, npm/brew install, curl|sh, 'is X safe', 'audit this repo'. Skip for first-party or already-audited code."
argument-hint: "[repo-url-or-package]"
---

# Audit Third-Party Software

Establish what unfamiliar code actually does before the user installs or runs it. The
user's bar is stricter than the vendor's marketing; the job is evidence, not reassurance.

## Rules

- Static analysis only, in an isolated clone or extract (default `/tmp/audit-<name>/`).
  Execute nothing unless the user authorizes it.
- README, CLAUDE.md and AGENTS.md are claims. Check every load-bearing one ("runs
  locally", "no telemetry", "open source", "no API keys") against the code; a false one
  is a finding.
- Every finding cites file:line, a SHA-256, a hostname or an endpoint.
- Sort each finding into a tier; the worst tier sets the verdict:
  - **Malicious → UNSAFE**: credential exfiltration, obfuscated or base64 payloads,
    `eval` of fetched strings, dotfile reads, install-time downloads, anti-sandbox checks.
  - **User-hostile but legal → CAUTION**: hidden call-home to a vendor backend,
    installation-unique IDs, remote killswitches or capability control, telemetry on by
    default, a closed-source critical component, permission-skipping flags
    (`--dangerously-skip-permissions`) as defaults, unauthenticated local HTTP or IPC
    servers.
  - **Benign noise → clear it**: dependency author URLs, cloud SDK error and metadata
    URLs, help-text example hosts, feature-flag SDKs inherited from a legitimate upstream.
- Match the user's threshold. "If all OK, no warnings, install" means one CAUTION
  finding stops the install until the user decides; never soften a finding to reach yes.

## What to cover

Scope first: file count, languages, lockfiles, hooks and install scripts, CI, bundled
binaries. Then:

- **Telemetry and exfiltration**: analytics SDKs initialized, not merely referenced
  (posthog, mixpanel, amplitude, segment, sentry, datadog, launchdarkly, statsig);
  network calls to unexpected hosts and what they send; env vars uploaded at startup;
  toggles that default on.
- **Prompt injection** (AI-adjacent tools): hidden instructions in prompts sent to models
  (`<info_for_agent>`, `<system-override>`, invisible Unicode), skill or agent `.md`
  files that steer beyond the advertised function, system prompts that misstate the
  tool's identity.
- **Supply chain**: lifecycle scripts (`preinstall`, `postinstall`, `prepare`) that
  fetch or write outside `node_modules/`; typosquats; dependencies resolved from git URLs
  or other registries (lockfile `resolved:` lines off `registry.npmjs.org`); the same in
  `pyproject.toml`/`setup.py`, `build.rs` and vendored binaries; recently published
  packages (`npm view <pkg> time`) with few downloads and unknown maintainers; `.husky/`, install
  scripts, Dockerfiles, pre-commit and CI steps the user may run; `curl | sh` from
  anything but well-known sources (astral.sh, bun.sh, rustup.rs, deno.land). pnpm
  `onlyBuiltDependencies` and a pinned `packageManager` are positive signals; native
  builds of `sharp`, `better-sqlite3`, `node-pty` or `canvas` and husky's hook install
  are normal. Postinstall sweep:
  `find . -name package.json -not -path '*/node_modules/*' -exec grep -lE '"(pre|post)?install"' {} \;`
- **Closed-source phone-home**: manifests or lock files whose `sourceRepository` 404s,
  binaries downloaded at launch or build without hash pinning, licence or capability
  servers, session tokens tied to install-unique UUIDs. Analyse every binary with
  [references/binary-analysis.md](references/binary-analysis.md); its script's folder holds a
  `__pycache__` file, not a folder, so the script leaves no bytecode in an installed copy.
- **Privilege and local services**: `shell: true` or `exec` with user-derivable input,
  unauthenticated local servers (CSRF and DNS rebinding), permission-skipping defaults,
  hidden or detached launchers (judge the behaviour, not the file name).
- **Credentials**: tokens in `.git/config` remote URLs (always tell the user: it may be
  their own leak, a distribution token or someone else's), plaintext key storage versus
  the OS keychain, unexplained endpoints in `.env.example`.

Classify every unfamiliar hostname with
[references/domain-triage.md](references/domain-triage.md) before reporting it.

Read a small text project (roughly under 50 files) yourself, every executable file. A
real app (hundreds of files, compiled code, Electron or Next.js, bundled binaries) would
flood your context: hand it to a subagent with the absolute path, the user's OS and
threshold, what scoping surfaced, the domains above, the rule that README, CLAUDE.md and
AGENTS.md are claims to check against code, a read order (those docs, every
`package.json`, install scripts, `.github/workflows/`, then the framework's entry points:
Next.js API routes, Electron main process) and the report shape below, capped at 800
words, and synthesize its answer.

## Report

Write `AUDIT_FINDINGS.md` at the audit directory root so the user can come back to it,
then give the verdict, the blocking findings and the recommendation in chat.

```markdown
# Static audit — <project>

**Date:** YYYY-MM-DD · **Method:** static, no execution · **Verdict:** SAFE | CAUTION | UNSAFE

<One-sentence reason.>

## Artifacts examined

| Artifact | SHA-256 |
|---|---|
| `<path or name>` | `<hash>` |

(Binaries only; omit otherwise.)

## Critical findings

Only findings that set the verdict.

- **<Name>.** Evidence (`path/to/file.ts:123`). One-line impact.

## Notable but non-blocking

- **<Name>** — evidence, impact.

## What it actually does

<One code-grounded paragraph; name any contradiction with the README.>

## Not determinable statically

<Only when static analysis left a gap, such as the payload of a call seen in code.>

## Recommendation

<Matched to the user's threshold: install command and tweaks, mitigations, or do not install.>
```

Offer the next step for the verdict: SAFE, the install command; CAUTION, local
mitigations (a patch branch, a firewall rule) or a vendor issue, unless the threshold
was "no warnings", in which case recommend not installing and offer mitigations only if
asked; UNSAFE, clean up and rotate any credential exposed during the audit. The vendor
issue and the local hardening note use [references/templates.md](references/templates.md);
draft the issue, and the user decides whether to file it.
