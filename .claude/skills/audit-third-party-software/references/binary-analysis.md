# Binary analysis

For any compiled binary shipped with or downloaded by the audited software: which
endpoints it contacts, which runtime it embeds, and what else it does.

## Fingerprint

```bash
shasum -a 256 <binary>          # record it; a later audit detects a silent swap
file <binary>
codesign -dv <binary> 2>&1; codesign -d --entitlements - <binary> 2>&1   # macOS
otool -L <binary>               # macOS; on Linux: ldd, readelf -d
```

Ad-hoc signing without a team ID is context, not a finding; Developer ID plus
notarization means Apple has at least fingerprinted the vendor. `allow-jit`,
`allow-unsigned-executable-memory` and `disable-library-validation` are normal for
Electron and Node runtimes and worth noting in a CLI. Libraries beyond `libSystem`,
`libc++`, `libicucore` and `libresolv` deserve a look.

## Runtime

```bash
strings -a <binary> > /tmp/strings.txt
grep -m1 "bun-v" /tmp/strings.txt                        # Bun
grep -iE "^(NODE_SEA|nexe|pkg/[0-9])" /tmp/strings.txt   # Node SEA, pkg, nexe
grep -m1 "go1\." /tmp/strings.txt                        # Go
nm <binary> 2>/dev/null | grep -m1 _ZN4core              # Rust
```

Bun and Node SEA keep the JavaScript readable through `strings`, even minified; Go and
Rust give back far less.

## Endpoints

```bash
python3 scripts/extract_strings_urls.py /tmp/strings.txt   # path relative to the skill directory
```

The script dedupes URLs and hostnames and sets known-benign patterns aside. Triage the
rest with [domain-triage.md](domain-triage.md), reading a few hundred characters around
each occurrence of an unknown host to tell a vendor-controlled base URL from an
error-message, doc or help-text artifact.

## Session and capability patterns

In embedded JavaScript, especially in AI-adjacent tools:

- `POST .../session/guest` with a `client_id`: installation-unique tracking.
- A `refresh_token` and `access_token` pair: an OAuth-like session, often SaaS gating
  inside a "local" tool.
- Signed JWT claims such as `features`, `providers`, `models`, `killswitches`: remote
  capability control.
- `subject: {...}` in session responses: hints at what user data was sent.

When one appears, look for an opt-out:
`grep -iE "(DISABLE|OFFLINE|NO_TELEMETRY|LOCAL_ONLY)" /tmp/strings.txt`. No opt-out means
mandatory phone-home, a critical finding.

## Credentials and runtime behaviour

```bash
grep -oE "\"\\.(ssh|aws|gcp|azure|git-credentials|netrc|pgpass|docker)[^\"]*\"" /tmp/strings.txt | sort -u
grep -iE "keychain|CredentialStore|DPAPI|safeStorage" /tmp/strings.txt | head -20
grep -cE "\beval\s*\(|new Function\s*\(" /tmp/strings.txt
grep -cE "Buffer\.from\([^)]*,\s*['\"]base64" /tmp/strings.txt
grep -iE "VMWare|VirtualBox|QEMU|isDebuggerPresent" /tmp/strings.txt | head
```

A dotfile read the tool has no reason for is a finding; keychain use is usually a good
sign. `eval` counts in the low hundreds are normal for bundled React or Vue; more, or
`eval` near a base64 decode, means follow the code.

A benign binary that uses cloud SDKs looks alarming at first (hundreds of URLs, AWS and
GCP metadata endpoints); domain triage clears that noise.
