#!/usr/bin/env python3
"""Claude cloud for a colleague on plain Claude Code: no Omnigent, only this host's Claude Code login, git and gh.

    python3 scripts/claude_cloud.py setup [--secret-as-variable] [--no-proof]
    python3 scripts/claude_cloud.py start <task file> [--branch <b>]

``setup`` makes, or brings up to date, the colleague's own claude.ai cloud environment from the committed
``.claude/claude-cloud-environment.json`` (``name``, ``setup_script``, ``network``, ``variables``, ``registries``,
``proof``) through ``claude_environments.apply``, the code ``omnigent_agent.py claude-cloud-env`` shares; adds each
private registry's token as a network secret, which the session proxy puts on requests outside the VM, so the token
never reaches it; pins the checkout (``remote.defaultEnvironmentId`` in the untracked ``.claude/settings.local.json``);
and proves the result with one cloud run of the ``proof`` commands.

A registry's token comes from ``fnox -P claude-cloud get <secret>`` (``FNOX_AGE_KEY_FILE`` defaulting to
``~/.ssh/id_ed25519``), else a hidden prompt. It is never written to disk and never printed: every line this script
prints, and every request body but the network secret's own, is free of it and of its base64. The network-secret
endpoint is undocumented and sits behind ``Secrets``; when it fails, ``setup`` stops with the HTTP status and names
``--secret-as-variable``, which puts the token into the environment's variables instead, inside the VM.

``start`` is the route with no terminal: it pushes the branch, runs ``claude --cloud <task>`` under ``script`` (a
pseudo-terminal, since ``claude --cloud`` exits 1 without one), prints the session id and URL from the recorded
output and exits with claude's exit code. The session's results come back through the branch and its PR.

Standard library only, plus ``git``, ``gh``, ``claude``, ``script`` and, optionally, ``fnox``.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path


def _load_environments():
    path = Path(__file__).resolve().with_name("claude_environments.py")
    spec = importlib.util.spec_from_file_location(f"{__name__}_claude_environments", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENVS = _load_environments()
Refused = ENVS.Refused
SETTINGS = Path(".claude") / "settings.local.json"
PROFILE = "claude-cloud"  # the fnox profile holding a project's registry tokens
CREDENTIALS = "/v1/code/agent-proxy/environment-credentials"
PROOF_WAIT = 600  # seconds setup waits for the proof branch
PROOF_EVERY = 15
SESSION = re.compile(r"https://claude\.ai/code/(session_[A-Za-z0-9]+)")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\r")
MISSING = (
    "no cloud environment for this project: run `mise run claude-cloud:setup` (claude_cloud.py setup),"
    " or run the step locally"
)


def _run(*cmd: str, check: bool = True, **kw: object) -> subprocess.CompletedProcess:
    return ENVS._run(*cmd, check=check, **kw)


class Out:
    """What this script prints: each line has every secret it was told about cut out first."""

    def __init__(self, stream=None) -> None:
        self.secrets: list[str] = []
        self.stream = stream

    def hide(self, token: str) -> None:
        for value in (token, base64.b64encode(token.encode()).decode()):
            if value and value not in self.secrets:
                self.secrets.append(value)

    def clean(self, text: str) -> str:
        for value in self.secrets:
            text = text.replace(value, "[secret]")
        return text

    def __call__(self, line: str = "", err: bool = False) -> None:
        print(self.clean(line), file=sys.stderr if err else (self.stream or sys.stdout))


def token_of(
    registry: dict,
    run: Callable[..., subprocess.CompletedProcess],
    ask: Callable[[str], str],
    say: Out,
) -> str:
    """The token of ``registry`` (``{host, secret}``): from fnox's ``claude-cloud`` profile, else a hidden prompt."""
    env = {**os.environ}
    env.setdefault("FNOX_AGE_KEY_FILE", str(Path.home() / ".ssh" / "id_ed25519"))
    try:
        done = run("fnox", "-P", PROFILE, "get", registry["secret"], check=False, env=env)
    except OSError:
        done = None  # no fnox on this host
    token = (done.stdout or "").strip() if done is not None and done.returncode == 0 else ""
    if not token:
        say(
            f"{registry['host']}: no token from fnox (profile {PROFILE}, secret {registry['secret']}):"
            " asking instead"
        )
        try:
            token = ask(f"token for {registry['host']} (input hidden): ").strip()
        except EOFError:
            token = ""
    if not token:
        raise Refused(f"no token for {registry['host']}: fnox had none and nothing was typed")
    say.hide(token)
    return token


class Secrets:
    """The network-secret endpoint, the only place that knows its shape: if it changes, this is what changes."""

    def __init__(self, auth: dict, env_id: str, call: Callable[..., dict]) -> None:
        self.auth, self.env_id, self.call = auth, env_id, call

    def listing(self) -> list[dict]:
        found = self.call(f"{CREDENTIALS}?environment_id={self.env_id}", None, self.auth)
        rows = (
            found
            if isinstance(found, list)
            else next((v for v in found.values() if isinstance(v, list)), [])
        )
        return [r for r in rows if isinstance(r, dict)]

    def replace(self, host: str, token: str) -> None:
        """Delete the host's secret when there is one, then add ``token`` as its bearer: ``Authorization: Bearer
        base64(token)`` on requests to ``host``."""
        masked = (token, base64.b64encode(token.encode()).decode())
        for row in self.listing():
            if row.get("host") == host:
                ident = row.get("id") or row.get("credential_id")
                self.call(
                    f"{CREDENTIALS}/{ident}?environment_id={self.env_id}",
                    None,
                    self.auth,
                    masked,
                    "DELETE",
                )
        self.call(
            CREDENTIALS,
            {
                "environment_id": self.env_id,
                "host": host,
                "bearer": {
                    "header_name": "Authorization",
                    "prefix": "Bearer ",
                    "value": masked[1],
                },
            },
            self.auth,
            masked,
        )


def checkout(path: str = ".") -> Path:
    done = _run("git", "-C", path, "rev-parse", "--show-toplevel", check=False)
    if done.returncode:
        raise Refused(f"{path} is not inside a git checkout")
    return Path(done.stdout.strip())


def repo_name(root: Path) -> str:
    url = _run("git", "-C", str(root), "remote", "get-url", "origin", check=False).stdout.strip()
    name = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return name.removesuffix(".git")


def write_pin(root: Path, env_id: str) -> None:
    """``remote.defaultEnvironmentId`` in the untracked ``.claude/settings.local.json``, its other keys kept."""
    path = root / SETTINGS
    own = json.loads(path.read_text()) if path.exists() else {}
    remote = own.get("remote") if isinstance(own.get("remote"), dict) else {}
    own["remote"] = {**remote, "defaultEnvironmentId": env_id}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(own, indent=2) + "\n")


def pinned(root: Path) -> str:
    try:
        return str(json.loads((root / SETTINGS).read_text())["remote"]["defaultEnvironmentId"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def task_text(task: str, branch: str, push_to: str = "") -> str:
    """``task`` with what a session must do for its results to come back through the branch and its PR."""
    ask = (
        f"\n\nWork on branch {branch} (check it out first when you are not on it). When done, push your"
        f" commits to {push_to or branch} and post one comment on the branch's pull request (open a draft"
        " one when there is none) holding each command's exit code and every failure."
    )
    return task.rstrip() + ask


def proof_task(commands: list[str], user: str) -> str:
    target = f"claude-cloud-proof/{user}"
    listing = "\n".join(f"- `{c}`" for c in commands) or "- (none)"
    return (
        f"Run each of these commands from the repository root, in order, and note each one's exit code:\n"
        f"{listing}\n\nThen create the branch {target} from the current commit, add one empty commit whose"
        " message is one line per command, `<command>: exit <code>`, and push it to origin. Change nothing"
        " else and open no pull request."
    )


def start_session(
    task: str,
    root: Path,
    branch: str,
    run: Callable[..., subprocess.CompletedProcess],
    say: Out,
    platform: str = sys.platform,
) -> int:
    """Push ``branch``, run ``claude --cloud <task>`` under a pseudo-terminal, print its session id and URL, and
    return claude's exit code."""
    if not pinned(root):
        try:
            hit = ENVS.pick(ENVS.environments(ENVS.headers(run)), "", repo_name(root))
        except Refused:
            say(MISSING, err=True)
            return 2
        write_pin(root, str(hit["environment_id"]))
    run("git", "-C", str(root), "push", "-u", "origin", branch)
    cmd = ["claude", "--cloud", task]
    if platform == "darwin":
        wrapped = ["script", "-q", "/dev/null", *cmd]
    else:
        wrapped = ["script", "-qec", shlex.join(cmd), "/dev/null"]
    done = run(*wrapped, check=False, cwd=str(root), stdin=subprocess.DEVNULL)
    seen = ANSI.sub("", done.stdout or "")
    hit = SESSION.search(seen)
    if hit:
        say(f"session {hit.group(1)}")
        say(f"url {hit.group(0)}")
    else:
        say("no session URL in claude's output; its last lines:", err=True)
        say("\n".join(seen.strip().splitlines()[-5:]), err=True)
    return done.returncode


def prove(
    definition: dict,
    root: Path,
    run: Callable[..., subprocess.CompletedProcess],
    say: Out,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """One cloud run of the definition's ``proof`` commands: the session pushes an empty commit to
    ``claude-cloud-proof/<github user>`` whose message lists each exit code; poll that branch, print the codes,
    delete it. 0 when every code is 0."""
    commands = definition.get("proof") or []
    if not commands:
        say("no proof commands in the definition: skipped")
        return 0
    user = run("gh", "api", "user", "--jq", ".login").stdout.strip()
    branch = _run("git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    ref = f"claude-cloud-proof/{user}"
    origin = ["git", "-C", str(root)]

    def remote_head() -> str:
        out = run(*origin, "ls-remote", "origin", f"refs/heads/{ref}", check=False).stdout.split()
        return out[0] if out else ""

    if remote_head():  # an earlier run's
        run(*origin, "push", "origin", "--delete", ref)
    code = start_session(proof_task(commands, user), root, branch, run, say)
    if code:
        raise Refused(f"the proof run did not start: claude exited {code}")
    end = clock() + PROOF_WAIT
    while not remote_head():
        if clock() >= end:
            raise Refused(
                f"the proof branch {ref} did not appear in {PROOF_WAIT // 60} minutes: the session may"
                " still be running, see claude.ai/code"
            )
        sleep(PROOF_EVERY)
    run(*origin, "fetch", "-q", "origin", ref)
    message = run(*origin, "log", "-1", "--format=%B", "FETCH_HEAD").stdout.strip()
    run(*origin, "push", "origin", "--delete", ref)
    bad = 0
    for line in message.splitlines():
        say(f"proof: {line}")
        found = re.search(r"exit (\d+)\s*$", line)
        bad += bool(found and found.group(1) != "0")
    return 1 if bad or not message else 0


def setup(
    flag: bool,
    proof: bool = True,
    path: str = ".",
    run: Callable[..., subprocess.CompletedProcess] = _run,
    ask: Callable[[str], str] = getpass.getpass,
    say: Out | None = None,
    call: Callable[..., dict] | None = None,
    **proving: object,
) -> int:
    say = say or Out()
    try:
        root = checkout(path)
        text = ENVS.committed(root, ENVS.DEFINITION)
        if text is None:
            raise Refused(
                f"{root} has no {ENVS.DEFINITION} committed at HEAD: commit the definition"
            )
        definition = ENVS.definition_of(text)
        found = ENVS.committed_script(root, definition.get("setup_script") or "")
        if found is None:
            found = ENVS.committed_script(root)
        if found is None:
            raise Refused(
                f"{root} has no setup script committed ({ENVS.SETUP_SCRIPTS[0]}, or the definition's"
                " `setup_script`)"
            )
        script_path, script = found
        name = definition.get("name") or repo_name(root)
        if not name:
            raise Refused(f"{root} has no origin remote to name the environment after: set `name`")
        registries = definition.get("registries") or []
        tokens = {r["host"]: token_of(r, run, ask, say) for r in registries}
        variables = dict(definition.get("variables") or {})
        if flag:
            for r in registries:
                variables[r["secret"]] = tokens[r["host"]]
        secrets = tuple(t for t in tokens.values())
        auth = ENVS.headers(run, say.hide)
        action, env = ENVS.apply(
            auth,
            name,
            script,
            f"Cloud sessions of {name}, set up by {script_path}",
            {**definition, "variables": variables},
            masked=secrets,
        )
        say(f"{action} cloud environment {name} ({env}) from {script_path}")
        if registries and not flag:
            secret_api = Secrets(auth, env, call or ENVS.call)
            try:
                for r in registries:
                    secret_api.replace(r["host"], tokens[r["host"]])
                    say(f"network secret for {r['host']} set")
            except Refused as e:
                say(f"setup stopped: the network-secret endpoint failed: {e}", err=True)
                say(
                    "the endpoint is undocumented and may have changed; --secret-as-variable stores the token"
                    " as an environment variable instead, which puts it inside the VM",
                    err=True,
                )
                return 1
        elif registries:
            say(
                "the token is now inside the VM: each registry's secret is an environment variable of"
                f" {name}, readable by every session in it"
            )
        write_pin(root, env)
        say(f"pinned {root / SETTINGS} to environment {name} ({env})")
        if proof:
            return prove(definition, root, run, say, **proving)  # type: ignore[arg-type]
        return 0
    except Refused as e:
        say(f"claude-cloud setup: {e}", err=True)
        return 1


def start(
    task_file: str,
    branch: str = "",
    path: str = ".",
    run: Callable[..., subprocess.CompletedProcess] = _run,
    say: Out | None = None,
) -> int:
    say = say or Out()
    try:
        root = checkout(path)
        branch = (
            branch
            or _run("git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        )
        if branch == "HEAD":
            raise Refused("a detached HEAD has no branch to push: check one out or pass --branch")
        task = Path(task_file).read_text()
        return start_session(task_text(task, branch), root, branch, run, say)
    except (Refused, OSError) as e:
        say(f"claude-cloud start: {e}", err=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser(
        "setup", help="make or update the cloud environment, its secrets and pin, and prove it"
    )
    s.add_argument(
        "--secret-as-variable",
        action="store_true",
        help="put a registry's token in the VM's variables",
    )
    s.add_argument("--no-proof", action="store_true", help="skip the proof run")
    st = sub.add_parser("start", help="start a cloud session from a task file, with no terminal")
    st.add_argument("task_file")
    st.add_argument("--branch", default="")
    args = p.parse_args(argv)
    if args.cmd == "setup":
        return setup(args.secret_as_variable, proof=not args.no_proof)
    return start(args.task_file, args.branch)


if __name__ == "__main__":
    sys.exit(main())
