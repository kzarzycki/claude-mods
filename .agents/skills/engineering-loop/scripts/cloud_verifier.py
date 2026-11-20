#!/usr/bin/env python3
"""Run a Codex verifier inside a Claude cloud session's VM, on a login the host seeds once (SKILL.md, Cloud worker).

On the host that starts cloud sessions:

    python3 scripts/cloud_verifier.py login            # once: a device login into a Codex home kept only for seeding
    python3 scripts/cloud_verifier.py seed [--env ID]...  # before starting a session whose VM will verify

In the VM, from the checkout:

    python3 <skill>/scripts/cloud_verifier.py verify --pr N --brief FILE [--harness codex|claude] [--model M] [--effort E]

On a host with no worker VM (route 1b), a Codex Cloud thread driven with the host's own login:

    python3 scripts/cloud_verifier.py thread --pr N --brief FILE [--model M] [--effort E] [--thread ID --env ID] [--head SHA]

`thread-exec --thread ID --env ID -- CMD` runs a command in a thread's VM without a model turn.
`thread` starts a thread, checks out the PR's head in its VM, sends the brief as a turn and writes the report (read
back from the thread's checkout, else its final message; one without a `SATISFIED:` line is not written) at the
brief's `- Report:` path. Exit 0 report written, 1 no report, 3 the verifier stopped on a question (written at `<report>.question`), 2 route 1b unusable (the endpoint is undocumented):
use route 2 or the host verifier. No token is sent to the VM.

No command prints a secret's value: each one (`$CODEX_AUTH_JSON` and the tokens it decodes to, the host's and the seed
home's login tokens, the Claude Code token, the thread route's token) is registered where it is read, and everything
on stdout and stderr, a traceback and the verifier's own output included, is printed with any run of 8 or more of a
secret's characters as `[secret]`. A refused seed is described by length, hash and days left
(`CODEX_AUTH_JSON: 2412 chars, sha256 3f2a9c1e`), which is enough to tell a missing, stale or refused one apart.

`login` runs `codex login --device-auth` with CODEX_HOME at the seed home (`$CODEX_CLOUD_HOME`, else
`~/.codex-cloud`), a login of its own for when the host's cannot be used.

`seed` stores a copy of a Codex login in the cloud environment, as the variable CODEX_AUTH_JSON (base64). It takes
the host's own login (`$CODEX_HOME`, else `~/.codex/auth.json`) when that is a ChatGPT login whose access token has
at least `--host-min-days` (default 1) left. When it has under `--host-refresh-days` left (default 3), it is first
refreshed in place, the way the Codex CLI does it, and written back to the host's `auth.json` in one atomic replace:
Codex processes on the host re-read that file before their own refresh and after a 401, and the CLI refreshes only
within 5 minutes of expiry, so a refresh days earlier never races one. A refused refresh exits 2, naming the host
login and `codex login` to run. Otherwise the host file is only read. Without a host login to use it uses the seed home's login and,
when its access token has under `--min-days` left (default 5 of its 10), refreshes it the way the Codex CLI does and
writes the new tokens back to the seed home, never to the host's file, however the two homes alias. Either copy carries no refresh token, so no VM can rotate a login, and
a VM whose copy has expired fails with a 401 instead of breaking the login for the others. It also adds OpenAI's hosts to the environment's allowed hosts. The environment is `--env`, given once per
environment to seed several in one run, else the checkout's `.claude/settings.local.json` pin
(`remote.defaultEnvironmentId`), read from the main checkout when run in a worktree. A variable is set when a session
starts, so seed before starting the session. Exit 2 means no login can be seeded: its text names the host login and
the seed home's, each missing or too short, or the refused refresh, and the owner runs `login` (or `codex login` on
the host) again. Exit 1 means an environment could not be seeded: each is still tried, and the failed ones are named.

To keep the host login and every environment fresh without the owner, run `seed --env A --env B` every 2 days as an
Omnigent scheduled task on the host that holds the login, on a small model, keeping the run (`sys_session_keep`)
when it exits non-zero, so a failure surfaces while the login still has days left.

`verify` installs the Codex CLI when the VM lacks it, writes the seeded login to `~/.codex/auth.json` when Codex is
not logged in, and refuses a tree with uncommitted changes, since a verifier reviews a pushed head only (files in the
report's own folder pass: a fresh clone ignores `tmp/loop/` only where the project's own .gitignore does). It checks
out the PR's head detached, so nothing the verifier does moves the worker's branch, runs `codex exec` on the brief with Codex's own sandbox
off (the VM is the sandbox, and the verifier needs Docker and the network), under an `AGENT_SIGNATURE=` line
naming the model and effort it was given, and posts the report as one comment on
the PR through REST, unchanged, printing the comment's URL as its last line. With `--harness claude` it runs
`claude -p` on the brief instead, in permission mode `bypassPermissions` for the same reason, on the session's own
Claude login (no install, no login step, no seeded variable), and keeps what it prints on stdout as the final
message; `--effort` is refused there (exit 2), since the CLI has no such flag. The report is the file the brief's
`- Report: <path>` line names (approvals.py brief), else the CLI's final message, else the file inside the checkout that message links; one without a `SATISFIED:` line is
not posted, and a report or question file counts only when this pass wrote it, so an earlier pass's file is never
posted again and none is deleted. A verifier that stops on a question (`<report>.question`, verifier.md) gets that file posted
instead, headed `## Verifier question`. It returns the checkout to where it was. When the verifier left
a change outside that folder, the script deletes and restores nothing, since git can't say which leftover hides an
older file: the checkout stays as it is, the changes are named on stderr, and the exit is 4.
Neither checkout replaces an ignored file: where one is in the way, the first is refused (exit 2) and the second
leaves the checkout as it is (exit 4).
Where the checkout of the PR's head itself shows changes (a submodule the PR moved, a file only the worker's branch
ignores), the pass is refused and the checkout returned (exit 2), since an edit to one of those could not be told
apart. A change is what `git status` shows: an edit to a file git ignores can't be seen and is not reported.
Exit 0 report posted, 1 the pass failed (the CLI failed, wrote no report, or the comment could not be posted), 2 a
precondition is missing and nothing was touched, 3 a question posted, 4 the checkout needs a look, whatever else the
pass did (a posted comment's URL is still printed).
The carrier session runs it detached and polls, since a foreground command in the VM stops at 10 minutes.

Standard library only, plus `gh`, `git` and `npm` (or `claude`, for `--harness claude`) in the VM and `codex` and the Claude Code login on the host.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

VAR = "CODEX_AUTH_JSON"
HOSTS = ["chatgpt.com", "*.chatgpt.com", "auth.openai.com", "api.openai.com"]
# ponytail: the refresh call mirrors the Codex CLI's own (codex-rs/login/src/auth/manager.rs: the endpoint, the
# CLI's public client id, a JSON body), because the CLI only refreshes a token within 5 minutes of expiry and a
# seed has to refresh days earlier. If OpenAI changes the call, `seed` exits 2 and `login` starts over.
REFRESH_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CLAUDE_API = os.environ.get("CLAUDE_CLOUD_API_BASE", "https://api.anthropic.com")


class Refused(Exception):
    """A precondition is missing; the message says what to do."""


class Redactor:
    """The secrets this run has read, and a text with every run of `MIN` or more of their characters masked."""

    MIN = 8

    def __init__(self) -> None:
        self.secrets: set[str] = set()
        self.grams: set[str] = set()

    def add(self, *values: object) -> None:
        for value in values:
            if isinstance(value, str) and len(value) >= self.MIN and value not in self.secrets:
                self.secrets.add(value)
                self.grams.update(value[i : i + self.MIN] for i in range(len(value) - self.MIN + 1))

    def login(self, auth: object) -> None:
        """Every token of a Codex login."""
        tokens = auth.get("tokens") if isinstance(auth, dict) else None
        self.add(*(tokens.values() if isinstance(tokens, dict) else ()))

    def seed(self, value: str) -> None:
        """The seeded variable and the tokens it decodes to, whatever state it is in."""
        self.add(value)
        try:
            self.login(json.loads(base64.b64decode(value)))
        except ValueError:
            pass

    def __call__(self, text: str) -> str:
        out, i, n = [], 0, self.MIN
        while i < len(text):
            if text[i : i + n] in self.grams:
                end = i + n
                while end < len(text) and any(text[i : end + 1] in s for s in self.secrets):
                    end += 1
                out.append("[secret]")
                i = end
            else:
                out.append(text[i])
                i += 1
        return "".join(out)


REDACT = Redactor()


class Redacting(io.TextIOBase):
    """A stream that holds output to the end of each line and writes it redacted, so a secret split over two writes
    is still caught."""

    def __init__(self, stream) -> None:
        self.stream, self.held = stream, ""

    def write(self, s: str) -> int:
        *lines, self.held = (self.held + s).split("\n")
        if lines:
            self.stream.write("".join(REDACT(line) + "\n" for line in lines))
        return len(s)

    def flush(self) -> None:  # a partial line stays held: it may end in half a secret
        self.stream.flush()

    def end(self) -> None:
        if self.held:
            self.stream.write(REDACT(self.held))
            self.held = ""
        self.stream.flush()

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


def describe(name: str, value: str) -> str:
    """A secret as the person debugging it can check it without seeing it."""
    return f"{name}: {len(value)} chars, sha256 {hashlib.sha256(value.encode()).hexdigest()[:8]}"


def seed_home() -> Path:
    return Path(os.environ.get("CODEX_CLOUD_HOME") or Path.home() / ".codex-cloud")


def run(*cmd: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    # errors=replace: a file name that is no UTF-8 must show in a status, not fail the read
    done = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False, **kw)
    if check and done.returncode:
        raise Refused(
            f"`{' '.join(cmd)}` exited {done.returncode}: {(done.stderr or done.stdout).strip()[-600:]}"
        )
    return done


def expires_at(access_token: str) -> float:
    """The `exp` claim of a JWT, in epoch seconds."""
    payload = access_token.split(".")[1]
    return float(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"])


def reader_copy(auth: dict) -> dict:
    """The login as a VM gets it: the same tokens without the refresh token."""
    return {**auth, "tokens": {**auth["tokens"], "refresh_token": ""}}


def post_json(url: str, body: dict | None, headers: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.load(resp)


# ── host: login and seed ─────────────────────────────────────────────────────────────────────────────────────────


def login() -> int:
    home = seed_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return subprocess.run(
        ["codex", "login", "--device-auth"],
        env={**os.environ, "CODEX_HOME": str(home)},
        check=False,
    ).returncode


def refreshed(
    auth: dict, who: str = "the seed login", fix: str = "run `cloud_verifier.py login`"
) -> dict:
    """The login with new tokens from OpenAI's auth service, as the Codex CLI's refresh makes them; a refusal names
    `who` was refused and the `fix`."""
    try:
        new = post_json(
            REFRESH_URL,
            {
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": auth["tokens"]["refresh_token"],
            },
            {},
        )
    except urllib.error.HTTPError as e:
        # the body may echo credential material: report the status and the error code only
        try:
            code = json.loads(e.read()).get("error")
        except ValueError:
            code = None
        code = code.get("code") if isinstance(code, dict) else code
        raise Refused(f"the refresh of {who} was refused (HTTP {e.code}, {code}): {fix}")
    REDACT.add(*new.values())
    tokens = {**auth["tokens"], **{k: v for k, v in new.items() if k in auth["tokens"] and v}}
    return {
        **auth,
        "tokens": tokens,
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime()),
    }


def claude_headers() -> dict:
    """Headers for Claude's environment API, on the Claude Code login this host already has."""
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
    REDACT.add(oauth.get("accessToken"), oauth.get("refreshToken"))
    if oauth.get("expiresAt", 0) / 1000 < time.time() + 60:
        raise Refused(
            "the Claude Code login's token has expired: run `claude` once to refresh it, then seed again"
        )
    org = json.loads(run("claude", "auth", "status", "--json").stdout)["orgId"]
    return {
        "Authorization": f"Bearer {oauth['accessToken']}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "ccr-byoc-2025-07-29",
        "x-organization-uuid": org,
    }


def pinned_environment() -> str:
    common = Path(
        run("git", "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    )
    for root in (Path(run("git", "rev-parse", "--show-toplevel").stdout.strip()), common.parent):
        pin = root / ".claude" / "settings.local.json"
        if pin.exists() and (
            env := json.loads(pin.read_text()).get("remote", {}).get("defaultEnvironmentId")
        ):
            return env
    raise Refused("no cloud environment: pass --env, or pin one in .claude/settings.local.json")


def host_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def replace_login(path: Path, auth: dict) -> None:
    """Write the login to `path` in one step: a `.tmp` beside it, mode 0600, then a replace, so a reader sees the old
    login or the new one, never half of one, and the new refresh token replaces the spent one at once."""
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # a `.tmp` left by an earlier run keeps its mode through O_CREAT
    with os.fdopen(fd, "w") as out:
        out.write(json.dumps(auth, indent=2))
    tmp.replace(path)


def host_login() -> tuple[dict | None, str]:
    """The host's own Codex login and, when it can't be used, why: a ChatGPT login with an access token."""
    path = host_home() / "auth.json"
    if not path.exists():
        return None, f"no host login at {path}"
    try:
        auth = json.loads(path.read_text())
        REDACT.login(auth)
        expires_at(auth["tokens"]["access_token"])
    except (ValueError, KeyError, IndexError, TypeError):
        return None, f"the host login at {path} is not a ChatGPT login with an access token"
    return auth, str(path)


def seed_login(min_days: float) -> dict:
    """The seed home's login, refreshed in place when it is running out."""
    path = seed_home() / "auth.json"
    if not path.exists():
        raise Refused(f"no seed login at {path}: run `cloud_verifier.py login`")
    auth = json.loads(path.read_text())
    REDACT.login(auth)
    if not (auth.get("tokens") or {}).get("refresh_token"):
        raise Refused(
            f"{path} is not a ChatGPT login with a refresh token: run `cloud_verifier.py login`"
        )
    if expires_at(auth["tokens"]["access_token"]) - time.time() < min_days * 86400:
        auth = refreshed(auth)
        replace_login(path, auth)
        print("refreshed the seed login")
    return auth


def days_left(auth: dict) -> float:
    return (expires_at(auth["tokens"]["access_token"]) - time.time()) / 86400


def seed(
    envs: list[str] | None,
    min_days: float,
    host_min_days: float = 1,
    host_refresh_days: float = 3,
) -> int:
    auth, where = host_login()
    if auth and days_left(auth) < host_refresh_days and not auth["tokens"].get("refresh_token"):
        # a scheduled run must not pass quietly on a login it cannot renew: fail while days remain
        raise Refused(
            f"the host login at {where} has under {host_refresh_days:g} days left and no refresh"
            " token to renew it: run `codex login` on this host, then seed again"
        )
    if auth and days_left(auth) < host_refresh_days:
        # the one deliberate write of the host's file: Codex on this host re-reads it before its own refresh
        auth = refreshed(
            auth,
            f"the host login at {where}",
            "run `codex login` on this host, then seed again",
        )
        replace_login(Path(where), auth)
        print(f"refreshed the host login at {where}")
    if auth and expires_at(auth["tokens"]["access_token"]) - time.time() >= host_min_days * 86400:
        print("using the host's Codex login (no refresh token stored)")
    else:
        if auth:
            where = f"the host login at {where} has under {host_min_days:g} days left"
        try:
            if seed_home().resolve() == host_home().resolve():
                # the fallback refreshes in place: never on the host's own file, however the two paths alias
                raise Refused("the seed home is the host's own Codex home, so it is not refreshed")
            auth = seed_login(min_days)
        except Refused as e:
            raise Refused(f"no usable Codex login: {where}; and {e}")
    headers = claude_headers()
    failed = []
    for env in envs or [pinned_environment()]:
        try:
            store(env, auth, headers)
        except (
            Refused,
            OSError,
            ValueError,
            KeyError,
        ) as e:  # the next environment is still seeded
            print(f"cloud_verifier: seeding {env} failed: {e}", file=sys.stderr)
            failed.append(env)
    if failed:
        print(f"cloud_verifier: not seeded: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


def store(env: str, auth: dict, headers: dict) -> None:
    """Put the login's reader copy and OpenAI's hosts into one cloud environment."""
    url = f"{CLAUDE_API}/v1/environment_providers/{env}"
    current = post_json(url, None, headers)
    config = current["config"]
    copy = base64.b64encode(json.dumps(reader_copy(auth)).encode()).decode()
    REDACT.add(copy)
    config["environment"] = {**(config.get("environment") or {}), VAR: copy}
    net = config.setdefault("network_config", {})
    net["allowed_hosts"] = sorted(set(net.get("allowed_hosts") or []) | set(HOSTS))
    post_json(
        url,
        {"name": current["name"], "description": current.get("description", ""), "config": config},
        headers,
    )
    print(
        f"seeded {current['name']} ({env}): the login there lasts {days_left(auth):.1f} more days"
    )


# ── VM: verify ───────────────────────────────────────────────────────────────────────────────────────────────────


def ensure_codex() -> None:
    if not shutil.which("codex"):
        run("npm", "install", "-g", "-s", "@openai/codex")
    if run("codex", "login", "status", check=False).returncode == 0:
        return
    if not (seeded := os.environ.get(VAR)):
        raise Refused(
            f"Codex is not logged in and ${VAR} is not set: run `cloud_verifier.py seed` on the host, then start a new session"
        )
    try:
        left = (
            f"its access token has {days_left(json.loads(base64.b64decode(seeded))):.1f} days left"
        )
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise Refused(
            f"${VAR} is not a base64 ChatGPT login ({describe(VAR, seeded)}): seed again on the host"
        ) from None
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    auth = home / "auth.json"
    auth.touch(mode=0o600)
    auth.write_bytes(base64.b64decode(seeded))
    if run("codex", "login", "status", check=False).returncode:
        raise Refused(
            f"Codex does not accept the login in ${VAR} ({describe(VAR, seeded)}; {left}): seed again on the host"
        )


def report_path(brief: str) -> Path | None:
    found = re.search(r"^- Report: (\S+)$", brief, re.MULTILINE)
    return Path(found[1]) if found else None


def signature(model: str | None, effort: str | None, harness: str = "codex") -> str:
    """`codex/<model>/<effort>` (`cc/...` for Claude) as orchestrating-agents' launcher writes it atop a brief
    (`gpt-6.1-terra` is `terra-6.1`, `claude-sonnet-5-5` is `sonnet-5.5`, `medium` is `med`, `?` for the CLI's own
    default), so the report's `Verifier:` line names what ran."""
    short = re.sub(r"^(gpt|claude)-", "", model or "")
    if found := re.fullmatch(r"(\d+)[.-](\d+)-([a-z]+)", short):
        short = f"{found[3]}-{found[1]}.{found[2]}"
    elif found := re.fullmatch(r"([a-z]+)-(\d+)-(\d+)", short):
        short = f"{found[1]}-{found[2]}.{found[3]}"
    name = {"claude": "cc"}.get(harness, harness)
    return f"{name}/{short or '?'}/{ {'medium': 'med'}.get(effort or '', effort) or '?' }"


def changes(report: Path | None) -> list[tuple[str, str]]:
    """(status, path) of every uncommitted path but the pass's own: the report, its question and the untracked
    files in the report's folder, where the proof logs live and which a fresh clone ignores only where the project's
    .gitignore does. Run from the top of the checkout, since git names paths from there."""
    own, keep = set(), None
    if report and not report.is_absolute():
        own = {report.as_posix(), f"{report.as_posix()}.question"}
        keep = f"{report.parent.as_posix()}/" if report.parent != Path() else None
    fields = iter(
        run("git", "status", "--porcelain", "-z", "--untracked-files=all").stdout.split("\0")
    )
    found = []
    for field in fields:
        if not field:
            continue
        status, path = field[:2], field[3:]
        if status[0] in "RC":
            next(fields, None)  # a rename's or copy's source follows as a field of its own
        if not (status == "??" and (path in own or (keep and path.startswith(keep)))):
            found.append((status, path))
    return found


def uncommitted(report: Path | None) -> str:
    return "\n".join(f"{status} {path}" for status, path in changes(report))


def showing(report: Path | None) -> str:
    """What git shows as changed, or why it could not say: a status that fails is a tree to look at, not a clean one."""
    try:
        return uncommitted(report)
    except Refused as e:
        return str(e)


def returned(was: str, report: Path | None) -> str:
    """Check out where the pass started: '' when the tree is back there and clean, else what stands in the way."""
    back = run("git", "checkout", "-q", "--no-overwrite-ignore", was, check=False)
    if back.returncode:
        return back.stderr.strip() or f"`git checkout {was}` exited {back.returncode}"
    return showing(report)  # clean there before the pass, so a change still showing is the pass's


def written(path: Path) -> int | None:
    """When the file was last written, or None when there is none."""
    return path.stat().st_mtime_ns if path.is_file() else None


def text(path: Path) -> str:
    """The file as it is, line ends included; a byte that is no UTF-8 is shown as such instead of failing the pass."""
    return path.read_bytes().decode("utf-8", "replace") if path.is_file() else ""


ANSWERED = re.compile(r"^## Answer to your question\s*$", re.MULTILINE)
NEW_IN_ANSWER = re.compile(r"^New in the answer:[ \t]*\S", re.MULTILINE)


def repeat_ask(brief: str, ask: str) -> str:
    """The reason a question is not handed to the lead, else "". A brief carrying the lead's marked answer section
    (`## Answer to your question`, lead.md) says this pass already had a question answered, so a new one must name
    what the answer made necessary on a `New in the answer:` line (verifier.md): without it the verifier left runs
    out of its first question, and each repeat costs another cloud run and heavy-slot hold."""
    if ANSWERED.search(brief) and not NEW_IN_ANSWER.search(ask):
        return (
            "the brief carries the lead's answer to an earlier question, and the new question has no "
            "`New in the answer:` line, so it is not passed on; list every run the pass needs in one question "
            "(verifier.md), or name the log of the answer that made another necessary"
        )
    return ""


def linked_files(final: str) -> list[str]:
    """What the final message names as a file: markdown link targets, then bare paths ending in .md, each once."""
    found = re.findall(r"\]\(([^)\s]+)\)", final) + re.findall(
        r"(?<![\w/.:-])([\w./-]+\.md)\b", final
    )
    return [f for i, f in enumerate(found) if "://" not in f and f not in found[:i]]


def linked_report(final: str, root: Path) -> tuple[str, str] | None:
    """The first file the final message names, inside `root`, that holds a `SATISFIED:` line, with its path.
    A path that resolves outside `root` (an absolute one, `..`, a symlink out) is never read."""
    top = root.resolve()
    for name in linked_files(final):
        path = (top / name).resolve()
        if top in path.parents and path.is_file():
            body = text(path)
            if re.search(r"^SATISFIED:", body, re.MULTILINE):
                return str(path.relative_to(top)), body
    return None


def relay_exec(cmd: list[str], brief: str, keep: Path | None = None) -> int:
    """Run a verifier CLI on the brief (stdin) without the seeded variable (Codex reads the auth.json `verify` wrote,
    Claude its own login), its output relayed line by line through this process's redacted stdout and stderr, so a
    verifier can neither read the variable nor print a token. With `keep`, what it prints on stdout (`claude -p`'s
    final message) is also written there, and its stderr is relayed apart, so a warning never joins the report."""
    env = {k: v for k, v in os.environ.items() if k != VAR}
    child = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if keep else subprocess.STDOUT,
        text=True,
        errors="replace",
        env=env,
    )
    # no `with`: closing the pipe would wait on the relay thread, which waits on any descendant holding it
    assert child.stdin and child.stdout

    def feed() -> None:  # beside the relay, so neither pipe fills while the other waits
        try:
            child.stdin.write(brief)
            child.stdin.close()
        except OSError:  # the CLI exited before reading it all: its exit says so
            pass

    kept: list[str] = []

    def relay(stream, to, into: list[str] | None) -> None:
        for line in stream:
            to.write(line)
            to.flush()
            if into is not None:
                into.append(line)

    # The streams are bound now, while `main` has the redactor in place: a line that arrives after
    # `main` has put the real streams back must still go through it.
    threads = [threading.Thread(target=feed, daemon=True)]
    threads.append(
        threading.Thread(
            target=relay, args=(child.stdout, sys.stdout, kept if keep else None), daemon=True
        )
    )
    if keep and child.stderr:
        threads.append(
            threading.Thread(target=relay, args=(child.stderr, sys.stderr, None), daemon=True)
        )
    for thread in threads:
        thread.start()
    code = child.wait()
    # a background descendant of the CLI can hold the pipe open long after it exits: wait only briefly for the tail
    for thread in threads:
        thread.join(2)
    if keep:
        keep.write_text("".join(kept))
    return code


def codex_exec(cmd: list[str], brief: str) -> int:
    """Run Codex on the brief; it writes its final message to the file its `-o` names."""
    return relay_exec(cmd, brief)


def needs_a_look(why: str, what: str) -> None:
    print(
        f"cloud_verifier: {why}; look and put it back before the next pass:\n{what}",
        file=sys.stderr,
    )


def verify(
    pr: int, brief_file: Path, model: str | None, effort: str | None, harness: str = "codex"
) -> int:
    if harness == "claude" and effort:
        raise Refused("`--effort` is Codex's only: the Claude CLI has no effort flag, so pass none")
    brief = brief_file.read_text()
    if not brief.startswith("AGENT_SIGNATURE="):
        brief = f"AGENT_SIGNATURE={signature(model, effort, harness)}\n{brief}"
    os.chdir(run("git", "rev-parse", "--show-toplevel").stdout.strip())
    if harness == "codex":
        ensure_codex()
    report = report_path(brief)
    question = report.with_name(report.name + ".question") if report else None
    final = Path(tempfile.mkdtemp(prefix="cloud-verifier-")) / "final.md"
    if dirty := uncommitted(report):
        raise Refused(
            f"the tree has uncommitted changes, and a verifier reviews a pushed head only:\n{dirty[:600]}"
        )
    pull = json.loads(run("gh", "api", f"repos/{{owner}}/{{repo}}/pulls/{pr}").stdout)
    head, ref = pull["head"]["sha"], pull["head"]["ref"]
    was = (
        run("git", "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
        or run("git", "rev-parse", "HEAD").stdout.strip()
    )
    if run("git", "rev-parse", "HEAD").stdout.strip() != head:
        run("git", "fetch", "-q", "origin", ref)
    # always detached, so a commit or a branch switch by the verifier never moves the worker's branch; and never
    # over an ignored file, which git's checkout replaces by default and the status above can't see
    went = run("git", "checkout", "-q", "--no-overwrite-ignore", "--detach", head, check=False)
    if went.returncode:
        why = went.stderr.strip() or f"exit {went.returncode}"
        if half := showing(report):  # it failed part way, as a filter or a full disk makes it
            needs_a_look(f"`git checkout {head}` failed part way ({why[-300:]})", half)
            return 4
        raise Refused(f"`git checkout {head}` was refused: {why[-600:]}")
    # The tree must be clean at the head too, so that any change after the pass is the verifier's. Comparing with
    # what the checkout itself shows (a submodule the PR moved, a file only the worker's branch ignores) would
    # miss an edit to one of those, so such a checkout is returned and refused instead.
    if shown := showing(report):
        if still := returned(was, report):
            needs_a_look("the checkout could not be returned", still)
            return 4
        raise Refused(
            "at the PR's head this checkout shows changes of its own, and a verifier reviews the pushed head only; "
            f"put them right (update a submodule, move a file aside) and run the pass again:\n{shown[:600]}"
        )
    if harness == "claude":
        # the VM is the sandbox, as for Codex below; the final message is what `-p` prints on stdout
        cmd = ["claude", "-p", "--permission-mode", "bypassPermissions", "--output-format", "text"]
        cmd += ["--model", model] if model else []
    else:
        cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(final)]
        cmd += ["-m", model] if model else []
        cmd += ["-c", f"model_reasoning_effort={effort}"] if effort else []
    # an earlier pass's file is not this pass's answer: one counts only when this pass wrote it
    before = {p: written(p) for p in (report, question) if p}
    code, wrote, stuck = 1, {}, ""
    try:
        started = time.time()
        code = (
            relay_exec(cmd, brief, final) if harness == "claude" else codex_exec([*cmd, "-"], brief)
        )
        print(f"{harness} exited {code} after {time.time() - started:.0f} s", flush=True)
        # read before the checkout back, which rewrites a report path that both commits track
        wrote = {
            p: text(p) for p in (report, question) if p and written(p) not in (None, before[p])
        }
        wrote[final] = text(final)
        # A verdict of its own in the report file, else in the final message, wins. Failing both, the CLI may have
        # written the report elsewhere and ended on a link to it: read it before the checkout goes back.
        if not re.search(r"^SATISFIED:", wrote.get(report, ""), re.MULTILINE):
            if re.search(r"^SATISFIED:", wrote[final], re.MULTILINE):
                wrote.pop(report, None)
            elif linked := linked_report(wrote[final], Path.cwd()):
                print(f"the report is read from {linked[0]}, which the final message names")
                wrote[final] = linked[1]
                wrote.pop(report, None)
    finally:
        # The script never deletes or restores a file: git can't say which leftover hides something older (an
        # ignored file, a folder with its own repository), so a tree the verifier changed stays as it is,
        # detached at the PR's head, for someone to look at.
        stuck = showing(report) or returned(was, report)
        if stuck:
            needs_a_look("the pass left the checkout changed, so it stays as it is", stuck)
    ask, body = (
        wrote.get(question, ""),
        wrote.get(report, "").strip() and wrote[report] or wrote[final],
    )
    try:
        if not code and ask.strip() and (why := repeat_ask(brief, ask)):
            print(f"cloud_verifier: {why}", file=sys.stderr)
            return 4 if stuck else 1
        if not code and ask.strip():
            # verifier.md: a verifier that needs something from the lead writes <report>.question and stops
            print(post(pr, f"## Verifier question\n\n{ask}"))
            return 4 if stuck else 3
        if code or not re.search(r"^SATISFIED:", body, re.MULTILINE):
            print(
                f"no report with a SATISFIED: line ({harness} exit {code}); the last of what it wrote:\n{body[-1500:]}"
            )
            return 4 if stuck else 1
        print(post(pr, body))
    except (Refused, OSError, ValueError) as e:  # not posted, so a failed pass
        print(f"cloud_verifier: {e}", file=sys.stderr)
        return 4 if stuck else 1
    return 4 if stuck else 0


def post(pr: int, body: str) -> str:
    """Post one comment on the PR through REST (GraphQL answers 403 in the VM) and return its URL."""
    posted = run(
        "gh",
        "api",
        f"repos/{{owner}}/{{repo}}/issues/{pr}/comments",
        "-F",
        "body=@-",  # from stdin: a long report does not fit an argument
        "--jq",
        ".html_url",
        input=body,
    )
    return posted.stdout.strip()


# ── host: a Codex Cloud thread as the verifier's machine (route 1b) ───────────────────────────────────────────────
# ponytail: the endpoint, its subprotocol login and the cloud-only fields of `thread/start` are read from the ChatGPT
# web app (docs/knowledge/codex-verifier-in-the-cloud.md, route 1b), so they can change without notice. Every
# surprise raises Unusable, `thread` exits 2 and the lead falls back to route 2 or a host verifier, never to no
# verifier. Upgrade path: OpenAI's access tokens for automation, if they cover Cloud threads.

WS_URL = os.environ.get("CODEX_CLOUD_WS", "wss://codex-cloud-backend.chatgpt.com/")
USAGE_URL = os.environ.get("CODEX_CLOUD_USAGE", "https://chatgpt.com/backend-api/wham/usage")


class Unusable(Refused):
    """Route 1b does not answer as the probe saw it: use route 2 or the host verifier."""


class Socket:
    """A WebSocket client of text frames, standard library only: just what a JSON-RPC conversation needs."""

    def __init__(self, url: str, token: str) -> None:
        u = urllib.parse.urlparse(url)
        raw = socket.create_connection(
            (u.hostname, u.port or (443 if u.scheme == "wss" else 80)), timeout=60
        )
        self.sock = (
            ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
            if u.scheme == "wss"
            else raw
        )
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                f"GET {u.path or '/'} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: https://chatgpt.com\r\n"
                f"Sec-WebSocket-Protocol: codex-app-server, openai-bearer.{token}\r\n\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            more = self.sock.recv(4096)
            if not more:
                break
            head += more
        self.buf = head.partition(b"\r\n\r\n")[2]
        status = head.split(b"\r\n")[0].decode(errors="replace")
        if " 101 " not in status:
            raise Unusable(f"the endpoint refused the WebSocket: {status}")

    def need(self, n: int) -> bytes:
        while len(self.buf) < n:
            more = self.sock.recv(65536)
            if not more:
                raise Unusable("the endpoint closed the connection")
            self.buf += more
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        size = (
            bytes([0x80 | n])
            if n < 126
            else b"\xfe" + n.to_bytes(2, "big")
            if n < 65536
            else b"\xff" + n.to_bytes(8, "big")
        )
        self.sock.sendall(
            b"\x81" + size + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        )

    def recv(self) -> dict:
        text = b""
        while True:
            b0, b1 = self.need(2)
            n = b1 & 0x7F
            n = (
                int.from_bytes(self.need(2), "big")
                if n == 126
                else int.from_bytes(self.need(8), "big")
                if n == 127
                else n
            )
            data = self.need(n)
            op = b0 & 0x0F
            if op == 8:
                raise Unusable("the endpoint closed the connection")
            if (
                op == 9
            ):  # ping: answer with the same bytes (a client frame is masked; a zero mask is a valid one)
                self.sock.sendall(b"\x8a" + bytes([0x80 | len(data)]) + b"\0\0\0\0" + data)
            elif op in (0, 1):
                text += data
                if b0 & 0x80:
                    msg = json.loads(text)
                    if not isinstance(msg, dict):
                        raise Unusable(f"the endpoint sent {type(msg).__name__}, not an object")
                    return msg


class Rpc:
    def __init__(self, token: str) -> None:
        try:
            self.ws = Socket(WS_URL, token)
        except OSError as e:
            raise Unusable(f"no connection to {WS_URL}: {e}") from e
        self.n = 0
        self.notes: list[dict] = []
        self.call("initialize", {"clientInfo": {"name": "cloud_verifier", "version": "1"}})
        self.ws.send({"method": "initialized"})

    def call(self, method: str, params: dict) -> dict:
        self.n += 1
        self.ws.send({"id": self.n, "method": method, "params": params})
        while True:
            msg = self.ws.recv()
            if msg.get("id") == self.n and "method" not in msg:
                if "error" in msg:
                    raise Unusable(f"{method} failed: {str(msg['error'])[:300]}")
                return msg.get("result") or {}
            if "method" in msg:
                self.notes.append(msg)

    def until(self, method: str, timeout: float) -> dict:
        """The next notification named `method`, with every other one kept in `notes`."""
        end = time.time() + timeout
        while time.time() < end:
            for i, note in enumerate(self.notes):
                if note["method"] == method:
                    return self.notes.pop(i)
            self.ws.sock.settimeout(max(1.0, end - time.time()))
            try:
                self.notes.append(self.ws.recv())
            except TimeoutError:
                break
        raise Unusable(f"no {method} within {int(timeout)} s")


def host_token() -> str:
    auth, why = host_login()
    if not auth:
        raise Unusable(f"route 1b needs the host's own Codex login: {why}")
    if expires_at(auth["tokens"]["access_token"]) < time.time() + 600:
        raise Unusable("the host's Codex login has run out: run `codex login` on the host")
    return auth["tokens"]["access_token"]


def quota(token: str) -> str:
    """The weekly Codex allowance used, as the endpoint states it ('?' when it does not)."""
    try:
        req = urllib.request.Request(USAGE_URL, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.load(resp)
        return json.dumps(body.get("rate_limit", body))[:300]
    except (OSError, ValueError, AttributeError):
        return "?"


def thread_start(rpc: Rpc, model: str | None, effort: str | None) -> tuple[str, str]:
    cfg = {"model_reasoning_effort": effort} if effort else {}
    got = rpc.call(
        "thread/start",
        {
            "model": model,
            "config": cfg,
            "sandbox": "danger-full-access",
            "approvalPolicy": "never",
            "serviceName": "codex_cloud",
            "environments": [{"environmentConfigId": None}],
        },
    )
    try:
        thread = got["thread"]["id"]
    except (KeyError, TypeError) as e:
        raise Unusable(f"thread/start answered without a thread id: {str(got)[:200]}") from e
    return thread, next(iter(got["thread"].get("environments") or [{}]), {}).get(
        "environmentId", ""
    )


def thread_exec(rpc: Rpc, thread: str, env: str, command: str) -> tuple[int, str]:
    got = rpc.call(
        "command/exec",
        {"threadId": thread, "environmentId": env, "command": ["bash", "-lc", command]},
    )
    return int(got.get("exitCode", 1)), (got.get("stdout") or "") + (got.get("stderr") or "")


def thread_turn(
    rpc: Rpc, thread: str, text: str, model: str | None, effort: str | None, timeout: float
) -> str:
    """Send a turn and return the thread's final message once the turn completes."""
    turn = {
        "threadId": thread,
        "clientUserMessageId": str(uuid.uuid4()),
        "input": [{"type": "text", "text": text}],
        "model": model,
        "approvalPolicy": "never",
        "sandboxPolicy": {
            "type": "dangerFullAccess"
        },  # the thread's VM is the sandbox; a verifier needs Docker and writes
        "collaborationMode": {
            "mode": "default",
            "settings": {"model": model, "reasoning_effort": effort},
        },
    }
    before = newest_item(rpc, thread)
    rpc.call("turn/addUserMessage", turn)
    done = rpc.until("turn/completed", timeout)
    status = ((done.get("params") or {}).get("turn") or {}).get("status", "completed")
    if status != "completed":
        raise Unusable(f"the turn ended as {status}")
    rpc.notes.clear()
    for item in thread_items(rpc, thread):
        if item["id"] == before:
            break
        if item.get("type") == "agentMessage":
            return item.get("text") or ""
    return ""  # nothing new from this turn: never an earlier turn's message


def thread_items(rpc: Rpc, thread: str) -> list[dict]:
    got = rpc.call("thread/items/list", {"threadId": thread, "limit": 30, "sortDirection": "desc"})
    return [x["item"] for x in got.get("data") or []]


def newest_item(rpc: Rpc, thread: str) -> str:
    return next(iter(thread_items(rpc, thread)), {}).get("id", "")


def thread_verify(
    pr: int,
    brief_file: Path,
    model: str | None,
    effort: str | None,
    thread: str | None,
    env: str,
    pending_head: str | None = None,
) -> int:
    """One pass on a Codex Cloud thread: clone the PR head (a later pass reuses the thread's checkout), run the brief,
    read the report back from the thread's checkout, else take its final message, and write it at the brief's path."""
    brief = brief_file.read_text()
    out = report_path(brief)
    token = host_token()
    print(f"quota before: {quota(token)}")
    rpc = Rpc(token)
    if not thread:
        thread, env = thread_start(rpc, model, effort)
        print(f"thread {thread} env {env}")
    head = run(
        "gh",
        "pr",
        "view",
        str(pr),
        "--json",
        "headRefOid,headRepository,headRepositoryOwner",
        "--jq",
        '.headRefOid+" "+.headRepositoryOwner.login+"/"+.headRepository.name',
    ).stdout.split()
    head[0] = pending_head or head[0]
    code, said = thread_exec(
        rpc,
        thread,
        env,
        f"cd ~ && (test -d pr{pr} || gh repo clone {head[1]} pr{pr} -- -q) && cd pr{pr} "
        f"&& git fetch -q origin {head[0]} && git checkout -q --detach {head[0]} && mkdir -p tmp/loop && pwd",
    )
    if code:
        raise Unusable(f"the checkout of {head[0]} in the thread's VM failed: {said[-300:]}")
    checkout = said.strip().splitlines()[-1]
    if out:  # an earlier pass's report in a reused checkout is never this pass's
        stale = shlex.quote(f"{checkout}/{out}")
        code, said = thread_exec(rpc, thread, env, f"rm -f {stale} {stale}.question")
        if code:
            raise Unusable(f"could not clear the earlier report in the thread's VM: {said[-200:]}")
    final = thread_turn(
        rpc,
        thread,
        f"Your checkout is {checkout}, at the PR's head. Run from it.\n\n{brief}",
        model,
        effort,
        3600,
    )
    body = ""
    if out:
        code, body = thread_exec(rpc, thread, env, f"cat {shlex.quote(checkout + '/' + str(out))}")
        body = body if not code else ""
    body = body.strip() or final.strip()
    if (
        "SATISFIED:" not in body and "SATISFIED:" in final
    ):  # the final message's own verdict beats a link
        body = final.strip()
    print(f"quota after: {quota(token)}")
    if (
        out and "SATISFIED:" not in body
    ):  # a verifier that stops on a question writes `<report>.question` (verifier.md)
        code, asked = thread_exec(
            rpc, thread, env, f"cat {shlex.quote(checkout + '/' + str(out) + '.question')}"
        )
        if not code and asked.strip() and (why := repeat_ask(brief, asked)):
            print(f"cloud_verifier: {why}", file=sys.stderr)
            return 1
        if not code and asked.strip():
            out.parent.mkdir(parents=True, exist_ok=True)
            question = out.with_name(out.name + ".question")
            question.write_text(asked)
            print(question)
            return 3
    if "SATISFIED:" not in body:
        # the final message may end on a link to a report written elsewhere in the checkout (never outside it)
        top = shlex.quote(checkout)
        for name in linked_files(final):
            code, got = thread_exec(
                rpc,
                thread,
                env,
                f'cd {top} && p=$(realpath -- {shlex.quote(name)}) && test -f "$p" '
                f'&& case "$p" in "$(realpath .)"/*) cat "$p";; *) exit 1;; esac',
            )
            if not code and re.search(r"^SATISFIED:", got, re.MULTILINE):
                print(f"the report is read from {name}, which the final message names")
                body = got
                break
    if "SATISFIED:" not in body:
        print(
            f"the verifier wrote no report with a SATISFIED: line; its last message: {final.strip()[-500:]}",
            file=sys.stderr,
        )
        return 1
    target = out or Path(f"tmp/loop/pr{pr}-thread.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    body = re.sub(
        r"\A\s*Verifier:[^\n]*\n", "", body
    )  # the signature is the command line's, not the model's own claim
    nth = re.search(r"pass (\d+)", brief)
    target.write_text(
        f"Verifier: {signature(model, effort)}, pass {nth[1] if nth else 1}\n\n{body.strip()}\n"
    )
    print(target)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one command with stdout and stderr redacted: a secret's value never reaches the output, even in a
    traceback, which is printed here (exit 1, as Python gives an uncaught one) rather than raised past the writer."""
    REDACT.seed(os.environ.get(VAR, ""))
    out, err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = wrapped = Redacting(out), Redacting(err)
    try:
        return command(argv)
    except Exception:  # noqa: BLE001 - printed in full below, only through the redactor
        traceback.print_exc()
        return 1
    finally:
        for stream in wrapped:
            stream.end()
        sys.stdout, sys.stderr = out, err


def command(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="device login into the seed home (host, once)")
    s = sub.add_parser(
        "seed", help="refresh the seed login and store a copy in the cloud environment (host)"
    )
    s.add_argument(
        "--env",
        action="append",
        help="environment id, once per environment; default: the checkout's pinned one",
    )
    s.add_argument(
        "--min-days",
        type=float,
        default=5,
        help="refresh the seed login when its access token has fewer days left",
    )
    s.add_argument(
        "--host-min-days",
        type=float,
        default=1,
        help="use the host's own login when its access token has at least this many days left",
    )
    s.add_argument(
        "--host-refresh-days",
        type=float,
        default=3,
        help="refresh the host's own login in place when its access token has fewer days left",
    )
    v = sub.add_parser(
        "verify", help="run a Codex or Claude verifier pass on the PR and post its report (VM)"
    )
    v.add_argument("--pr", type=int, required=True)
    v.add_argument("--brief", type=Path, required=True)
    v.add_argument(
        "--harness",
        choices=["codex", "claude"],
        default="codex",
        help="the verifier's CLI: codex for a Claude-written PR, claude for a Codex-written one",
    )
    v.add_argument("--model")
    v.add_argument("--effort", help="Codex's reasoning effort; refused with --harness claude")
    t = sub.add_parser(
        "thread",
        help="run a Codex verifier pass on a Codex Cloud thread, driven from this host (route 1b)",
    )
    t.add_argument("--pr", type=int, required=True)
    t.add_argument("--brief", type=Path, required=True)
    t.add_argument("--model")
    t.add_argument("--effort")
    t.add_argument(
        "--thread", help="a thread a pass before it started: the later pass runs on its machine"
    )
    t.add_argument(
        "--head", help="check out this commit instead of the PR's head (a pass on an earlier head)"
    )
    t.add_argument(
        "--env", default="", help="that thread's environment id, printed by its first pass"
    )
    x = sub.add_parser(
        "thread-exec", help="run a shell command in a thread's VM, without a model turn"
    )
    x.add_argument("--thread", required=True)
    x.add_argument("--env", required=True)
    x.add_argument("cmd", nargs=argparse.REMAINDER, help="the command, after --")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            return login()
        if args.command == "seed":
            return seed(args.env, args.min_days, args.host_min_days, args.host_refresh_days)
        if args.command == "thread-exec":
            code, said = thread_exec(
                Rpc(host_token()),
                args.thread,
                args.env,
                shlex.join(args.cmd[args.cmd[:1] == ["--"] :]),
            )
            print(said, end="")
            return code
        if args.command == "thread":
            return thread_verify(
                args.pr, args.brief, args.model, args.effort, args.thread, args.env, args.head
            )
        return verify(args.pr, args.brief, args.model, args.effort, args.harness)
    except (Refused, OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        if not args.command.startswith("thread") and not isinstance(e, Refused):
            raise
        why = f"{e}" if isinstance(e, Refused) else f"unexpected answer from the endpoint: {e!r}"
        print(
            f"cloud_verifier: {why} (use route 2 or the host verifier)"
            if args.command.startswith("thread")
            else f"cloud_verifier: {why}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
