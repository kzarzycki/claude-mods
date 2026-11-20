"""claude.ai's cloud environments, on the Claude Code login this host already has.

The one client for `/v1/environment_providers`: `omnigent_agent.py` resolves and pins an environment with it and
makes one with `claude-cloud-env` (`cloud-env`), and engineering-loop's `cloud_verifier.py seed` stores its login with it. Not a command;
it is loaded by path, so a project's copy and an installed one never mix.

The token is read from the macOS keychain (`Claude Code-credentials`), else `~/.claude/.credentials.json`, and goes
only into a request's `Authorization` header: never into an argument list, a log or a message. An error names the
HTTP status and the server's own message with every secret this module was told about (`secret`) masked, since a
server can echo back what it was sent. `CLAUDE_CLOUD_API_BASE` replaces the API's base URL (a test's fake).

Standard library only, plus `claude` for the login's organization.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

PAGE = 100  # environments asked for per page; the listing follows `has_more` and `last_id`
PAGES = 20
DEFAULT = "Default"  # the environment Claude Code makes for an account's first cloud session


class Refused(Exception):
    """The login, the API or a lookup said no; the message says what to do."""


Run = Callable[..., subprocess.CompletedProcess]


def _run(*cmd: str, check: bool = True, **kw: object) -> subprocess.CompletedProcess:
    done = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False, **kw)
    if check and done.returncode:
        raise Refused(
            f"`{' '.join(cmd)}` exited {done.returncode}: {(done.stderr or done.stdout).strip()[-300:]}"
        )
    return done


def base() -> str:
    return os.environ.get("CLAUDE_CLOUD_API_BASE", "https://api.anthropic.com").rstrip("/")


def headers(run: Run = _run, secret: Callable[..., None] = lambda *_: None) -> dict:
    """Headers for the environment API on this host's Claude Code login. ``secret`` is handed each token as it is
    read, so a caller that redacts its output knows them; ``run`` runs ``security`` and ``claude``."""
    raw = ""
    if sys.platform == "darwin":
        user = os.environ.get("USER") or run("id", "-un").stdout.strip()
        raw = run(
            "security",
            "find-generic-password",
            "-a",
            user,
            "-s",
            "Claude Code-credentials",
            "-w",
            check=False,
        ).stdout
    if not raw and (path := Path.home() / ".claude" / ".credentials.json").exists():
        raw = path.read_text()
    if not raw:
        raise Refused("no Claude Code login on this host: run `claude auth login`")
    oauth = json.loads(raw)["claudeAiOauth"]
    secret(oauth.get("accessToken"), oauth.get("refreshToken"))
    if oauth.get("expiresAt", 0) / 1000 < time.time() + 60:
        raise Refused(
            "the Claude Code login's token has expired: run `claude` once to refresh it, then try again"
        )
    org = json.loads(run("claude", "auth", "status", "--json").stdout)["orgId"]
    return {
        "Authorization": f"Bearer {oauth['accessToken']}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "ccr-byoc-2025-07-29",
        "x-organization-uuid": org,
    }


def call(
    path: str,
    body: dict | None,
    auth: dict,
    masked: tuple[str, ...] = (),
    method: str = "",
) -> dict:
    """``GET`` ``path`` (``body`` None), else ``POST`` it as JSON; ``method`` (``DELETE``) replaces that choice. A
    refusal is a ``Refused`` naming the status and the server's message, with each of ``masked`` cut out of it."""
    verb = method or ("GET" if body is None else "POST")
    req = urllib.request.Request(
        base() + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **auth},
        method=verb,
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        said = e.read().decode(errors="replace")
        for value in (auth.get("Authorization", "").removeprefix("Bearer "), *masked):
            if value and len(value) >= 8:
                said = said.replace(value, "[secret]")
        said = said[-400:]  # cut after masking: a secret the cut splits would keep its tail
        path_only = path.split("?")[0]
        raise Refused(f"{verb} {path_only}: HTTP {e.code}: {said.strip()}") from None
    except urllib.error.URLError as e:
        raise Refused(f"{path.split('?')[0]}: {e.reason}") from None


def environments(auth: dict) -> list[dict]:
    """Every environment the login's organization holds, each with ``environment_id``, ``name`` and ``kind``."""
    found: list[dict] = []
    after = ""
    for _ in range(PAGES):
        query = urllib.parse.urlencode({"limit": PAGE, **({"after_id": after} if after else {})})
        page = call(f"/v1/environment_providers?{query}", None, auth)
        found += page.get("environments") or []
        after = page.get("last_id") or ""
        if page.get("has_more") is not True or not page.get("environments") or not after:
            break
    return found


def named(envs: list[dict], name: str) -> dict | None:
    """The one environment called ``name``; two of them is a ``Refused``, since either could be meant."""
    hits = [e for e in envs if e.get("name") == name]
    if len(hits) > 1:
        ids = ", ".join(str(e.get("environment_id")) for e in hits)
        raise Refused(
            f"{len(hits)} cloud environments are named {name!r} ({ids}): rename all but one"
        )
    return hits[0] if hits else None


def pick(envs: list[dict], env: str, repo: str) -> dict:
    """The environment a cloud session of ``repo`` runs in: the one called ``env`` when it is given, else the one
    named after the repository, else the account's ``Default``. A name that isn't there is refused, naming
    ``cloud-env``, which makes it."""
    make = (
        "create it with `claude_cloud.py setup` (a project's `mise run claude-cloud:setup`), or"
        " `omnigent_agent.py claude-cloud-env <checkout>` (from the checkout's .claude/claude-cloud-setup.sh)"
    )
    if env:
        if hit := named(envs, env):
            return hit
        raise Refused(f"no cloud environment named {env!r} on this host's claude login: {make}")
    for name in (repo, DEFAULT):
        if name and (hit := named(envs, name)):
            return hit
    raise Refused(
        f"no cloud environment named {repo!r} or {DEFAULT!r} on this host's claude login: {make}"
    )


def base_config(script: str) -> dict:
    """The config Claude Code gives its ``Default`` environment, with ``script`` as its setup script."""
    return {
        "environment_type": "anthropic",
        "cwd": "/home/user",
        "init_script": script,
        "environment": {},
        "languages": [
            {"name": "python", "version": "3.11"},
            {"name": "node", "version": "20"},
        ],
        "network_config": {"allowed_hosts": [], "allow_default_hosts": True},
    }


def create(
    auth: dict,
    name: str,
    script: str,
    description: str,
    definition: dict | None = None,
    masked: tuple[str, ...] = (),
) -> dict:
    """A new cloud environment called ``name`` with ``script`` as its setup script and, from ``definition``
    (``merged``), its network and variables; none without one, as Claude Code makes its ``Default`` one."""
    return call(
        "/v1/environment_providers/cloud/create",
        {
            "name": name,
            "kind": "anthropic_cloud",
            "description": description,
            "config": merged(base_config(script), script, definition or {}),
        },
        auth,
        masked=masked,
    )


def read(auth: dict, env_id: str) -> dict:
    return call(f"/v1/environment_providers/{env_id}", None, auth)


def update(
    auth: dict, env_id: str, current: dict, config: dict, masked: tuple[str, ...] = ()
) -> dict:
    """Replace ``env_id``'s config with ``config``, keeping its name and description; an update takes no
    ``kind``. The values of the variables ``current`` holds, and ``masked``, are masked in a refusal."""
    variables = (current.get("config") or {}).get("environment") or {}
    return call(
        f"/v1/environment_providers/{env_id}",
        {"name": current["name"], "description": current.get("description", ""), "config": config},
        auth,
        masked=(*(str(v) for v in variables.values()), *masked),
    )


# the committed files a project describes its cloud environment in; the older name of the script is still read
DEFINITION = ".claude/claude-cloud-environment.json"
SETUP_SCRIPTS = (".claude/claude-cloud-setup.sh", ".claude/cloud-setup.sh")
ACCESS = (
    "default",
    "none",
)  # network.access: the VM's default hosts allowed, or only the listed ones
TOKEN_PREFIXES = ("ghp_", "gho_", "ghs_", "ghu_", "ghr_", "github_pat_", "glpat-", "sk-", "xox")
LONG_SECRET = re.compile(r"[A-Za-z0-9+/_=-]{32,}")  # a long base64 or hex run, as a token is


def looks_secret(value: str) -> bool:
    return value.startswith(TOKEN_PREFIXES) or bool(LONG_SECRET.fullmatch(value))


def committed(root: str | Path, path: str, ref: str = "HEAD") -> str | None:
    """``path`` as commit ``ref`` of the repository at ``root`` holds it, None when it holds none: only a
    committed file is sent, so the environment never follows an unreviewed edit."""
    done = _run("git", "-C", str(root), "show", f"{ref}:{path}", check=False)
    return done.stdout if done.returncode == 0 else None


def committed_script(root: str | Path, wanted: str = "") -> tuple[str, str] | None:
    """The path and text of the setup script ``root``'s HEAD holds: ``wanted`` when given, else the first of
    ``SETUP_SCRIPTS`` that is committed."""
    for path in (wanted,) if wanted else SETUP_SCRIPTS:
        if (text := committed(root, path)) is not None:
            return path, text
    return None


def definition_of(text: str) -> dict:
    """The environment definition ``text`` holds, checked: ``variables`` non-secret strings only (a value that
    looks like a token is refused, since the variable sits inside the VM), ``network.access`` one of ``ACCESS``,
    ``registries`` a list of ``{host, secret}``."""
    try:
        found = json.loads(text)
    except ValueError as e:
        raise Refused(f"{DEFINITION} is not JSON: {e}") from None
    if not isinstance(found, dict):
        raise Refused(f"{DEFINITION} must hold a JSON object")
    variables = found.get("variables") or {}
    if not isinstance(variables, dict) or not all(isinstance(v, str) for v in variables.values()):
        raise Refused(f"{DEFINITION}: `variables` must map names to string values")
    for key, value in variables.items():
        if looks_secret(value):
            raise Refused(
                f"{DEFINITION}: variable {key} holds a value that looks like a token; variables"
                " sit inside the VM, so a secret goes in `registries` (a network secret) instead"
            )
    network = found.get("network") or {}
    if not isinstance(network, dict) or network.get("access", "default") not in ACCESS:
        raise Refused(f"{DEFINITION}: `network.access` must be one of {', '.join(ACCESS)}")
    hosts = network.get("allowed_hosts") or []
    if not isinstance(hosts, list) or not all(isinstance(h, str) for h in hosts):
        raise Refused(f"{DEFINITION}: `network.allowed_hosts` must be a list of host names")
    for reg in found.get("registries") or []:
        if not (
            isinstance(reg, dict)
            and isinstance(reg.get("host"), str)
            and isinstance(reg.get("secret"), str)
        ):
            raise Refused(f"{DEFINITION}: each of `registries` must be {{host, secret}}")
    proof = found.get("proof") or []
    if not isinstance(proof, list) or not all(isinstance(c, str) for c in proof):
        raise Refused(f"{DEFINITION}: `proof` must be a list of shell commands")
    return found


def merged(config: dict, script: str, definition: dict) -> dict:
    """``config`` with ``script`` as its setup script and ``definition``'s network and variables applied: the
    variables it names are set and every other variable stays (a colleague's own, a seeded login), and the
    registries' hosts are allowed, since a network secret reaches only a host the VM may call."""
    out = {**config, "init_script": script}
    if "network" in definition or definition.get("registries"):
        network = definition.get("network") or {}
        hosts = [
            *(network.get("allowed_hosts") or []),
            *(r["host"] for r in definition.get("registries") or []),
        ]
        out["network_config"] = {
            **(config.get("network_config") or {}),
            "allowed_hosts": list(dict.fromkeys(hosts)),
            "allow_default_hosts": network.get("access", "default") != "none",
        }
    if definition.get("variables"):
        out["environment"] = {**(config.get("environment") or {}), **definition["variables"]}
    return out


def apply(
    auth: dict,
    name: str,
    script: str,
    description: str,
    definition: dict | None = None,
    masked: tuple[str, ...] = (),
) -> tuple[str, str]:
    """Make the environment ``name`` from ``script`` and ``definition``, or bring the one there up to them: the
    one place `setup` and `cloud-env` both go through. Returns ``created``, ``updated`` or ``current`` and the
    environment's id."""
    found = named(environments(auth), name)
    if found is None:
        made = create(auth, name, script, description, definition, masked)
        return "created", str(made.get("environment_id", "?"))
    env = str(found["environment_id"])
    current = read(auth, env)
    config = dict(current.get("config") or {})
    wanted = merged(config, script, definition or {})
    if wanted == config:
        return "current", env
    update(auth, env, current, wanted, masked)
    return "updated", env
