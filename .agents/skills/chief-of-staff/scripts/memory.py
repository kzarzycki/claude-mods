#!/usr/bin/env python3
"""Recall from and retain into the project's Hindsight bank, when Hindsight is configured.

    memory.py recall <query>     print what the bank holds on <query>, one memory per line
    memory.py retain <text>      store <text> (an owner's preference or decision, verbatim)

The server and bank come from the Hindsight coding-agents config the hooks use
(``$HINDSIGHT_CONFIG``, else ``~/.hindsight/coding-agent.json``): ``apiUrl``, ``apiToken``,
``disabled`` and ``bankIdTemplate`` (``{gitProject}`` is the repo's name), so this script and
the hooks share one bank per repo. ``HINDSIGHT_API_URL`` overrides ``apiUrl``.

With no server configured, or ``disabled``, both commands print ``memory: not configured`` and
exit 0: the caller then works as it would without memory. A recall from a project with no bank yet
prints nothing. An unreachable server is a warning on
stderr and exit 0 for ``recall``, exit 1 for ``retain``, so a decision that was not stored is
not lost silently.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

TIMEOUT = 30  # seconds; a recall runs an LLM-free search, a retain only enqueues


def config() -> dict:
    path = Path(os.environ.get("HINDSIGHT_CONFIG") or Path.home() / ".hindsight/coding-agent.json")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    if os.environ.get("HINDSIGHT_API_URL"):
        data["apiUrl"] = os.environ["HINDSIGHT_API_URL"]
    return data


def repo_name() -> str:
    """The repo's name from its origin remote, else the current directory's name."""
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd().name
    return re.sub(r"\.git$", "", re.split(r"[/:]", url.rstrip("/"))[-1]) or Path.cwd().name


def bank(cfg: dict) -> str:
    return str(cfg.get("bankIdTemplate") or "coding-agent-{gitProject}").replace(
        "{gitProject}", repo_name()
    )


def call(cfg: dict, path: str, body: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if cfg.get("apiToken"):
        headers["Authorization"] = f"Bearer {cfg['apiToken']}"
    request = urllib.request.Request(
        str(cfg["apiUrl"]).rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read() or b"{}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("recall", "retain"):
        print("usage: memory.py recall|retain <text>", file=sys.stderr)
        return 2
    command, text = argv[0], " ".join(argv[1:])
    cfg = config()
    if not cfg.get("apiUrl") or cfg.get("disabled"):
        print("memory: not configured")
        return 0
    base = f"/v1/default/banks/{quote(bank(cfg), safe='')}/memories"
    try:
        if command == "recall":
            found = call(cfg, base + "/recall", {"query": text, "max_tokens": 2048})
            for item in found.get("results", []):
                print(" ".join(str(item.get("text", "")).split()))
        else:
            call(
                cfg,
                base,
                {"items": [{"content": text, "context": "chief of staff"}], "async": True},
            )
            print(f"memory: retained in {bank(cfg)}")
    except urllib.error.HTTPError as e:
        if command == "recall" and e.code == 404:  # a project's first recall: no bank yet
            return 0
        print(f"memory: unavailable ({e})", file=sys.stderr)
        return 1 if command == "retain" else 0
    except (OSError, ValueError) as e:
        print(f"memory: unavailable ({e})", file=sys.stderr)
        return 0 if command == "recall" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
