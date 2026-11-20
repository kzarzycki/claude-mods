#!/usr/bin/env python3
"""
Extract URLs and unique hostnames from a `strings` dump of a binary,
and classify them into benign / known-cloud-SDK / unknown buckets so
you can focus attention on the unknowns.

Usage:
    strings -a <binary> > /tmp/strings.txt
    python3 extract_strings_urls.py /tmp/strings.txt
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

URL_RE = re.compile(r'https?://[a-zA-Z0-9][a-zA-Z0-9.\-]+(?::[0-9]+)?(?:/[^\s"\'`]*)?')

# Known-benign hostname patterns — these appear in nearly every Node/Bun/Electron
# binary from legitimate upstream dependencies. Matching one of these doesn't
# clear a hostname entirely (a malicious binary could reference them too) but
# deprioritizes it in triage.
BENIGN_PATTERNS = [
    # Upstream dep author/homepage URLs that get embedded in bundled JS
    r"^plus-innovations\.com$",
    r"^feross\.org$",
    r"^sharp\.pixelplumbing\.com$",
    r"^react-native\.canny\.io$",
    r"^systeminformation\.io$",
    # Framework docs (referenced in comments)
    r"^(react|vue|svelte|angular|tailwindcss|ui\.shadcn|nextjs)\.",
    r"^react\.dev$",
    # Common package registries / docs
    r"^(registry\.)?npmjs\.org$",
    r"^nodejs\.org$",
    r"^goo\.gle$",
    r"^json-schema\.org$",
    r"^json\.schemastore\.org$",
    r"^www\.schemastore\.org$",
    # Example/test fixture domains
    r"^(example|another|evil)\.com$",
    r"^hooks\.example\.com$",
    r"^a\.co$",
    # Apache / W3C / standards
    r"^www\.apache\.org$",
    r"^www\.w3\.org$",
    r"^www\.apple\.com$",
    r"^bugs\.webkit\.org$",
    r"^grpc\.io$",
    # Cloud metadata servers
    r"^169\.254\.169\.254$",
    r"^169\.254\.170\.2$",
    r"^metadata\.google\.internal\.?$",
    r"^127\.0\.0\.1",
    r"^localhost",
    # Generic font CDN
    r"^fonts\.googleapis\.com$",
    r"^www\.gstatic\.com$",
    r"^cdn\.jsdelivr\.net$",
    # Bun runtime (baked into every Bun-compiled binary)
    r"^bun\.(com|sh|report)$",
    r"^debug\.bun\.sh$",
]

CLOUD_SDK_PATTERNS = [
    # AWS
    r"\.amazonaws\.com$",
    r"^bedrock-?",
    r"^cognito-identity-?",
    r"^sts-?",
    r"^oidc-?",
    r"^signin-?",
    r"^iamcredentials-?",
    r"^s3\.$",
    r"^cloudresourcemanager-?",
    r"^aws\.amazon\.com$",
    r"^docs\.aws\.amazon\.com$",
    # Google Cloud
    r"^cognito-identity\.amazonaws\.com$",
    r"^.*\.googleapis\.com$",
    r"^cloud\.google\.com$",
    r"^accounts\.google\.com$",
    r"^oauth2\.googleapis\.com$",
    r"^storage\.googleapis\.com$",
    r"^developers\.google\.com$",
    r"^policies\.google\.com$",
    # Azure / Microsoft
    r"^(login|signin)\.(microsoftonline|windows-ppe|chinacloudapi)\.",
    r"^aka\.ms$",
    r"^cognitiveservices\.azure\.com$",
    r"^learn\.microsoft\.com$",
    # AI platforms (legitimate; note but don't flag)
    r"^api\.anthropic\.com$",
    r"^(www\.)?anthropic\.com$",
    r"^claude(\.ai|\.com)$",
    r"^code\.claude\.com$",
    r"^docs\.claude\.com$",
    r"^platform\.claude\.com$",
    r"^downloads\.claude\.ai$",
    r"^clau\.de$",
    r"^support\.claude\.com$",
    r"^support\.anthropic\.com$",
    r"^docs\.anthropic\.com$",
    r"^apps\.apple\.com$",
    r"^api\.openai\.com$",
    r"^auth\.openai\.com$",
    r"^chatgpt\.com$",
    r"^openai\.com$",
    r"^cloudcode-pa\.googleapis\.com$",
    r"^generativelanguage\.googleapis\.com$",
    r"^aiplatform\.googleapis\.com$",
    # GitHub (for update/release checks, MCP catalogs)
    r"^(api\.|raw\.githubusercontent\.com|codeload\.)?github\.(com|io)$",
    r"^gist\.githubusercontent\.com$",
    r"^cli\.github\.com$",
    # Common feature flag / CDN services often inherited from upstream
    r"^cdn\.growthbook\.io$",
    # MCP ecosystem
    r"^mcp-proxy\.anthropic\.com$",
    r"^mcp\.sentry\.dev$",
    r"^registry\.modelcontextprotocol\.io$",
    r"^glama\.ai$",
    # Claude Code beacons (debug/staging)
    r"^beacon\.claude-ai\.staging\.ant\.dev$",
    r"^claude-ai\.staging\.ant\.dev$",
    r"^claude-staging\.fedstart\.com$",
    r"^claude\.fedstart\.com$",
    # React Native docs / Canny (AWS SDK errors reference this)
    r"^react-native\.canny\.io$",
    # Robohash, devicons etc. often inherited from avatar features
    r"^robohash\.org$",
]


def classify(host: str) -> str:
    for pat in BENIGN_PATTERNS:
        if re.search(pat, host):
            return "benign"
    for pat in CLOUD_SDK_PATTERNS:
        if re.search(pat, host):
            return "cloud-sdk"
    return "unknown"


def main(path: str) -> int:
    data = Path(path).read_text(errors="ignore")
    urls = sorted(set(URL_RE.findall(data)))

    hosts: dict[str, set[str]] = defaultdict(set)
    for url in urls:
        m = re.match(r"https?://([^/:\s]+)", url)
        if not m:
            continue
        host = m.group(1).lower().strip(".")
        if not host or "." not in host:
            continue
        hosts[host].add(url)

    buckets: dict[str, list[str]] = {"unknown": [], "cloud-sdk": [], "benign": []}
    for host in sorted(hosts):
        buckets[classify(host)].append(host)

    print(f"Total URLs extracted: {len(urls)}")
    print(f"Unique hostnames: {len(hosts)}")
    print()

    print("=== UNKNOWN (investigate each of these) ===")
    if not buckets["unknown"]:
        print("(none)")
    for host in buckets["unknown"]:
        sample = sorted(hosts[host])[0]
        print(f"  {host}  e.g. {sample[:120]}")
    print()

    print("=== CLOUD SDK / LEGITIMATE AI PLATFORM (usually fine) ===")
    for host in buckets["cloud-sdk"]:
        print(f"  {host}")
    print()

    print("=== BENIGN (upstream dep / standards / example) ===")
    for host in buckets["benign"]:
        print(f"  {host}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: extract_strings_urls.py <path-to-strings-output>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
