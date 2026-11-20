#!/usr/bin/env python3
"""A Claude Code PreToolUse hook on Bash: refuse a heavy test or check run on a host (#1233).

engineering-loop's SKILL.md, Where heavy steps run, sends a lead's own suite, build and check runs
to a Claude cloud session; this hook makes that the default. It reads the tool call's JSON on
stdin and refuses (exit 2, the reason on stderr, as Claude Code's PreToolUse contract takes it) a
command one of whose segments is heavy (``heavy``), when all of these hold:

- the session is not a cloud one (``CLAUDE_CODE_REMOTE`` is not ``true``);
- the call's ``cwd`` is inside a repository with ``docs/agents/loop.md``, whose ``Cloud worker:``
  line is not ``none`` (a project that keeps its workers on hosts runs there);
- the segment is not prefixed ``LOOP_HOST_RUN=<reason>`` (nor the whole command), the host
  fallback: the cloud route failed, or the run needs this host;
- the cloud route can run here: an Omnigent server is configured for this session
  (``RUNNER_SERVER_URL`` set). Without one (plain Claude Code) the run is allowed with one line on
  stderr saying it stayed on this machine, so nobody is blocked by a route they can't use.

The refusal names the ``claude-cloud-run`` call for that exact command and the fallback. Anything it
can't read or parse is allowed (exit 0), so a bug here never blocks work. Stdlib only, no
subprocess: it runs on every Bash call.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

LOOP_FILE = Path("docs") / "agents" / "loop.md"
NO_CLOUD = re.compile(r"^Cloud worker:[ \t]*none\b", re.MULTILINE | re.IGNORECASE)
HOST_RUN = "LOOP_HOST_RUN"
# the Omnigent server claude-cloud-run launches through; unset, the cloud route can't run here
RUNNER = "RUNNER_SERVER_URL"
NOTICE = (
    "heavy_run_guard: this test or check run stayed on this machine, since no Omnigent server is"
    f" configured for this session ({RUNNER} unset), so it can't go to a Claude cloud session; how to"
    " set up the cloud route is in engineering-loop's SKILL.md, Cloud worker."
)
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = {"&&", "||", ";", "|", "&", "|&", ";;", "(", ")", "\n"}
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][\w.-]*)\1")
# words a segment's real command follows: shell keywords and grouping, and wrappers that run the
# rest of the line as it is
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "nohup", "exec"}
# wrappers that run the command after their own options, by the options that take a value
WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "time": {"-f", "--format", "-o", "--output"},
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "--user", "--group"},
    "xargs": {"-n", "-I", "-P", "-L", "-d", "-a", "-s", "-E", "--max-args", "--max-procs"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
}
SHELLS = {"bash", "sh", "zsh", "dash"}
SHELL_DEPTH = 3  # nested ``sh -c`` strings judged; deeper ones are allowed
# pytest's reruns of the last failures read .pytest_cache, which a cloud clone has none of
LAST_FAILED = {"--lf", "--last-failed", "--ff", "--failed-first"}
# a ``cd <dir>`` step anywhere a command starts: the line's start, after an operator or a grouping
# character, after ``then``/``do``/``else``, or as the first word of a ``sh -c '...'`` string
CD_STEP = re.compile(
    r"(?:^|(?<=[;&|(){\n])|(?<=c ')|(?<=c \")|(?<=\bthen)|(?<=\bdo)|(?<=\belse))[ \t]*"
    r"(cd)[ \t]+((?:'[^']*'|\"[^\"]*\"|[^\s;&|'\"()])+)"
)
SEP_AFTER = re.compile(r"[ \t]*(?:&&|;)[ \t]*")
# a directory change the rewrite does not parse: options, ``pushd``/``popd``, ``builtin cd``, ``command cd``
UNPARSED_CD = re.compile(r"\b(?:pushd|popd)\b|\b(?:builtin|command)[ \t]+cd\b|\bcd[ \t]+-")
# pytest options that take the next word as their value, so it is no test path
PYTEST_VALUED = {
    "-k",
    "-m",
    "-p",
    "-c",
    "-o",
    "-W",
    "-r",
    "--deselect",
    "--ignore",
    "--ignore-glob",
    "--rootdir",
    "--confcutdir",
    "--basetemp",
    "--junitxml",
    "--junit-xml",
    "--maxfail",
    "--durations",
    "--tb",
    "--log-level",
    "--override-ini",
    "--import-mode",
    "--cov",
    "--cov-report",
}
UV_VALUED = {
    "--with",
    "--with-editable",
    "--with-requirements",
    "--project",
    "--directory",
    "--python",
    "-p",
    "--extra",
    "--group",
    "--env-file",
    "--package",
    "--index",
    "--from",
}
LAUNCHER = Path("skills") / "orchestrating-agents" / "scripts" / "omnigent_agent.py"


def repo_root(cwd: Path) -> Path | None:
    """The nearest directory at or above ``cwd`` holding ``.git`` (a checkout or a worktree)."""
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return None


def loop_repo(cwd: Path) -> Path | None:
    """The repository root when it runs the loop with cloud workers: it has ``docs/agents/loop.md``
    and no ``Cloud worker: none`` line there; else None."""
    root = repo_root(cwd)
    if root is None:
        return None
    try:
        text = (root / LOOP_FILE).read_text(errors="replace")
    except OSError:
        return None
    return None if NO_CLOUD.search(text) else root


def drop_heredocs(command: str) -> str:
    """``command`` without its here-documents' bodies, which are data, not commands."""
    out: list[str] = []
    ending: str | None = None
    for line in command.split("\n"):
        if ending is not None:
            if line.strip() == ending:
                ending = None
            continue
        out.append(line)
        if found := HEREDOC.search(line.replace("<<<", "   ")):
            ending = found.group(2)
    return "\n".join(out)


def segments(command: str) -> list[list[str]]:
    """The words of each simple command in ``command``, split at ``&&``, ``||``, ``;``, ``|``,
    ``&``, a newline and parentheses. Raises ValueError on a quote it can't close."""
    lex = shlex.shlex(drop_heredocs(command), posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = "#"
    parts: list[list[str]] = [[]]
    target = False  # the next word is a redirection's file, no argument
    for token in lex:
        if token in SEPARATORS or (token and set(token) <= set(";&|\n")):
            parts.append([])
            target = False
        elif token and set(token) <= set("<>&") and set(token) & set("<>"):
            if parts[-1] and parts[-1][-1].isdigit():  # the 2 of 2>file
                parts[-1].pop()
            target = True
        elif target:  # the file, or the 1 of 2>&1
            target = False
        else:
            parts[-1].append(token)
    return [p for p in parts if p]


def chdir(here: Path | None, target: str | None) -> Path | None:
    """The directory ``cd <target>`` moves to from ``here``; None when it can't be known (no
    target, ``-``, a variable or a substitution), and then nothing after it is judged."""
    if here is None or not target or target == "-" or "$" in target or "`" in target:
        return None
    path = Path(os.path.expanduser(target))
    if str(path).startswith("~"):
        return None
    return Path(os.path.normpath(path if path.is_absolute() else here / path))


def strip_leading(words: list[str], here: Path | None) -> tuple[list[str], bool, Path | None]:
    """The words after a segment's leading ``cd <dir>``, env assignments, shell keywords (``if``,
    ``then``, ``do``, ``!``, ``{`` and the like), ``nohup``, ``exec``, ``command`` and the wrappers
    in ``WRAPPERS`` with their options (and ``timeout``'s duration); whether a
    ``LOOP_HOST_RUN=<reason>`` assignment was among them; and the directory the rest runs in."""
    host = False
    i = 0
    while i < len(words):
        word = words[i]
        if ASSIGNMENT.match(word):
            name, _, value = word.partition("=")
            host |= name == HOST_RUN and bool(value.strip())
            i += 1
        elif word == "cd":
            here = chdir(here, words[i + 1] if i + 1 < len(words) else None)
            i += 2
        elif word in KEYWORDS:
            i += 1
        elif word == "command":  # ``command -v`` leaves ``-v`` first, which is no run
            i += 1
            while i < len(words) and words[i] == "-p":
                i += 1
        elif word in WRAPPERS:
            valued = WRAPPERS[word]
            i += 1
            while i < len(words) and words[i].startswith("-") and words[i] != "-":
                if words[i] == "--":
                    i += 1
                    break
                i += 2 if words[i] in valued else 1
            if word == "timeout":
                i += 1  # the duration
        else:
            break
    return words[i:], host, here


def shell_string(words: list[str]) -> str | None:
    """The command string of ``bash|sh|zsh|dash [options] -c <string>``, else None."""
    if not words or Path(words[0]).name not in SHELLS:
        return None
    i = 1
    while i < len(words) and words[i][:1] in "-+":
        word = words[i]
        if not word.startswith("--") and "c" in word[1:]:
            return words[i + 1] if i + 1 < len(words) else None
        i += 2 if word in ("-o", "+o") else 1
    return None


def is_test_path(word: str) -> bool:
    """Whether ``word`` names one test file or a node id in one (``path.py::Test::test``)."""
    return word.split("::", 1)[0].endswith(".py")


def heavy_pytest(args: list[str], here: Path) -> bool:
    """A pytest run is heavy when no word names a test file or node id, when a word is an existing
    directory (a suite), or with ``-n`` (xdist) or a rerun of the last failures (``--lf``, ``--ff``).
    An option's value never counts either way."""
    named = False
    i = 0
    while i < len(args):
        word = args[i]
        if word == "-n" or word.startswith("--numprocesses") or re.fullmatch(r"-n\S+", word):
            return True
        if word in LAST_FAILED:
            return True
        if word in PYTEST_VALUED:
            i += 2
            continue
        if not word.startswith("-"):
            if is_test_path(word):
                named = True
            elif (here / word).is_dir():
                return True
        i += 1
    return not named


def python_m_pytest(words: list[str]) -> list[str] | None:
    """The pytest arguments of ``python[3[.x]] -m pytest ...``, else None."""
    python = bool(words) and re.fullmatch(r"python(\d+(\.\d+)?)?", Path(words[0]).name)
    return words[3:] if python and words[1:3] == ["-m", "pytest"] else None


def after_uv_run(words: list[str]) -> list[str]:
    """The command ``uv run``, ``uv tool run`` or ``uvx`` runs (past their options), else ``words``."""
    name = Path(words[0]).name if words else ""
    if name == "uv" and words[1:2] == ["run"]:
        i = 2
    elif name == "uv" and words[1:3] == ["tool", "run"]:
        i = 3
    elif name == "uvx":
        i = 1
    else:
        return words
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "--":
            i += 1
            break
        i += 2 if words[i] in UV_VALUED else 1
    return words[i:]


def heavy(words: list[str], here: Path) -> bool:
    """Whether one segment's command (its leading words already stripped), run in ``here``, is a
    heavy run."""
    words = after_uv_run(words)
    if not words:
        return False
    prog = Path(words[0]).name
    args = words[1:]
    if (pytest_args := python_m_pytest(words)) is not None:
        return heavy_pytest(pytest_args, here)
    if prog == "pytest" or prog == "py.test":
        return heavy_pytest(args, here)
    if prog == "mise" and args[:1] in (["run"], ["r"]):
        tasks = [a for a in args[1:] if not a.startswith("-")]
        return any(t.startswith(("check", "test")) for t in tasks)
    if prog == "make":
        return any(a in ("check", "test") for a in args)
    if prog in ("npm", "pnpm", "yarn"):
        rest = args[1:] if args[:1] == ["run"] else args
        return rest[:1] == ["test"]
    if prog in ("cargo", "go"):
        return args[:1] == ["test"]
    if prog in ("tox", "nox"):
        return True
    if prog in ("gradle", "gradlew"):
        return any(a in ("test", "check", "build") for a in args)
    if prog in ("mvn", "mvnw"):
        return any(a in ("test", "verify") for a in args)
    for i, word in enumerate(words):
        if Path(word).name == "approvals.py":
            sub = words[i + 1 : i + 2]
            rest = words[i + 2 :]
            if sub == ["affected-tests"]:
                return True
            return sub == ["local-ci"] and any(a in ("--run", "--record") for a in rest)
    return False


def find_heavy(command: str, cwd: Path, depth: int = 0) -> Path | None:
    """The directory a heavy segment of ``command`` runs in, inside a loop repo (``loop_repo``),
    following each ``cd`` from ``cwd`` and judging a ``sh -c`` string as a command of its own; None
    when there is none. A segment after a ``cd`` it can't follow is not judged."""
    here: Path | None = cwd
    for words in segments(command):
        rest, host, here = strip_leading(words, here)
        if host or here is None or not rest:
            continue
        if (inner := shell_string(rest)) is not None:
            if depth < SHELL_DEPTH and (found := find_heavy(inner, here, depth + 1)):
                return found
            continue
        if heavy(rest, here) and loop_repo(here) is not None:
            return here
    return None


def cloud_command(command: str, cwd: Path, root: Path) -> str | None:
    """``command`` as the cloud session runs it from the checkout's root ``root``: every ``cd`` step,
    nested ``sh -c`` strings included, made relative to where the session is at that point (the
    first one to ``root``), and dropped when it moves nowhere; a command that starts in a
    subdirectory of ``root`` gets a ``cd`` there first. None when a ``cd`` can't be followed or leaves
    ``root``: the host path it names is not in the cloud clone, so the ``cd`` would fail there and
    its exit code would read as the command's own failure. As a net under every form it does not
    rewrite, also None when the result still names a host directory it knows (the call's, the
    root's, one a ``cd`` reached) or a directory change it does not parse (``UNPARSED_CD``), and when
    a ``cd`` inside a ``( … )`` group is followed by another, since the group's ``cd`` does not
    persist and the flat walk here would misplace the later one."""
    text = command.strip()
    host, vm = (
        cwd,
        root,
    )  # each cd is followed from where the host's shell is; the session starts at root
    prefix = ""
    if not CD_STEP.match(text) and cwd != root and cwd.is_relative_to(root):
        # it starts where the call is, which the clone has too
        prefix = f"cd {shlex.quote(os.path.relpath(cwd, root))} && "
        vm = cwd
    out: list[str] = []
    pos = 0
    followed = {cwd, root}
    grouped = False  # a cd seen inside a ( … ) group
    for found in CD_STEP.finditer(text):
        if found.start(1) < pos:
            continue
        if grouped:
            return None
        before = text[: found.start(1)]
        grouped = before.count("(") > before.count(")")
        try:
            target = shlex.split(found.group(2))[0]
        except (ValueError, IndexError):
            return None
        moved = chdir(host, target)
        if moved is None or not (moved == root or moved.is_relative_to(root)):
            return None
        step = os.path.relpath(moved, vm)
        host = vm = moved
        followed.add(moved)
        out.append(text[pos : found.start(1)])
        pos = found.end()
        if step == "." and (sep := SEP_AFTER.match(text, pos)):
            pos = sep.end()  # a cd that moves nowhere goes, with its separator
        else:
            out.append(f"cd {shlex.quote(step)}")
    run = prefix + "".join(out) + text[pos:]
    named = [str(d) for d in followed if len(d.parts) > 1]  # never the bare "/"
    if UNPARSED_CD.search(run) or any(d in run for d in named):
        return None
    return run


def launcher(root: Path) -> str:
    """Where orchestrating-agents' launcher is for this repository: the consumer's deployed skill,
    this pack's own copy beside the hook, else a placeholder naming it."""
    here = Path(__file__).resolve().parent
    for path in (
        root / ".claude" / LAUNCHER,
        root / ".agents" / LAUNCHER,
        root / "engineering" / LAUNCHER,
        here.parent / LAUNCHER,
    ):
        if path.is_file():
            return str(path)
    return "<orchestrating-agents>/scripts/omnigent_agent.py"


def refusal(command: str, cwd: Path, root: Path) -> str:
    """The reason the hook prints: the ``claude-cloud-run`` call for this exact command on the
    checkout ``root`` its heavy run lands in (its ``cd`` steps rewritten by ``cloud_command``), and
    the fallback; with a ``cd`` no cloud session can follow, the fallback alone, since a suggested
    call would fail as the command's own failure."""
    run = cloud_command(command, cwd, root)
    if run is None:
        head = (
            "Heavy run refused on this host: engineering-loop's SKILL.md, Where heavy steps run, sends"
            f" a test or check run to a Claude cloud session, but a `cd` in it goes outside {root} or"
            " can't be followed, so no claude-cloud-run call runs it as written. Rewrite it to run"
            f" inside that checkout, or, when it needs this host, run it with the reason as a prefix:"
            f" {HOST_RUN}=<reason> {command.strip()}"
        )
    else:
        call = (
            f"python3 {shlex.quote(launcher(root))} claude-cloud-run --checkout {shlex.quote(str(root))}"
            f" -- {shlex.quote(run)}"
        )
        head = (
            "Heavy run refused on this host: engineering-loop's SKILL.md, Where heavy steps run, sends"
            " a test or check run to a Claude cloud session. Run it there (commit and push first; it"
            " exits with the command's own code):\n"
            f"  {call}\n"
            f"If claude-cloud-run fails, or the run needs this host (a device, a `host` gate step), run it with"
            f" the reason as a prefix: {HOST_RUN}=<reason> {command.strip()}"
        )
    return head + (
        "\nThe cloud clone has no `.pytest_cache`, so `--lf` or `--ff` there runs the full selection."
        if LAST_FAILED & set(re.findall(r"--[\w-]+", command))
        else ""
    )


def verdict(payload: dict, env: dict[str, str]) -> tuple[int, str]:
    """The hook's exit code and stderr line for this tool call: ``(2, <refusal>)`` for a heavy run
    the cloud route could make, ``(0, NOTICE)`` for one it can't (no Omnigent server), else ``(0, "")``."""
    if env.get("CLAUDE_CODE_REMOTE") == "true":
        return 0, ""
    if payload.get("tool_name", "Bash") != "Bash":
        return 0, ""
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0, ""
    cwd = Path(payload.get("cwd") or os.getcwd())
    parts = segments(command)
    if parts and parts[0][0].startswith(HOST_RUN + "=") and parts[0][0].partition("=")[2].strip():
        return 0, ""  # the whole command starts with the fallback prefix
    place = find_heavy(command, cwd)
    root = loop_repo(place) if place else None
    if root is None:
        return 0, ""
    if not env.get(RUNNER):
        return 0, NOTICE
    return 2, refusal(command, cwd, root)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        code, line = verdict(payload, dict(os.environ)) if isinstance(payload, dict) else (0, "")
    except Exception:  # noqa: BLE001  (a parse bug must never block a command)
        return 0
    if line:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
