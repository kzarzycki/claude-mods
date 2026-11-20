#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Mutation check (engineering-loop): undo one production change at a time and see whether a test notices.

    uv run scripts/mutate.py --test '<command>' --log <path> <patch>...

Each patch undoes one change (verifier.md, Mutation-check the new tests, says how to write one). On a clean checkout
it applies each patch alone with `git apply`, runs the test command through the shell, records its exit code, undoes
the patch with `git apply -R` and checks the tree is clean again before the next one. A test command that fails has
killed the patch; one that passes means no test covers that change, and the patch survived. Two outcomes say nothing
about the patch and are `inconclusive`, never killed or survived: a test command that exits with the reserved code
(75, or the policy's `mutate.inconclusive_exit`) means setup failed, no verdict, and with `--built <path>` (repeatable,
globs: a file, or a directory hashed over every file under it) naming what the test command builds, a patch whose hashes
equal the head run's was never built into what the tests ran (`not built: inconclusive`). Hashes are taken after the
head run, which `--built` makes run even where the lane would run none, and after each patch's run; a glob that matches
nothing after the head run is refused. Without `--built` and the reserved code the log and exit codes are as before.

It refuses a tracked change or an untracked file that isn't ignored, the check `approvals.py local-ci` makes, so
patches under a gitignored `tmp/loop/` don't count, and it refuses any patch that doesn't apply before running a test,
and a head run (below) that leaves a change, which the first patch's restore would take for its own.
On SIGINT or SIGTERM it stops the test command, undoes the applied patch and then dies of that signal, so a killed run
leaves no mutation in the tree. The test command runs with PYTHONDONTWRITEBYTECODE=1, since a .pyc written in the
same second as its source would hide the next same-sized patch of that file.

Each test run takes a host gate slot (SKILL.md, One heavy gate per host slot): the heavy slot, an exclusive flock on
`${XDG_CACHE_HOME:-~/.cache}/engineering-loop/gate.<n>.lock` (the first free one of the host's `GATE_SLOTS`, as a project's gate takes), or the short lane,
`gate.short.lock` beside it, which waits only for another short job. Before any patch, the test command runs once on
the unmutated head in the short lane, timed: when it passes within the policy's `short_seconds` (default 120), every
patch runs in the short lane too, and otherwise, or when it fails, each takes the heavy slot. `short_seconds: 0` runs
no head run, and neither does a run already under a holder of the heavy slot: every patch takes the heavy slot. A run
waits for its slot with a `waiting for the host gate slot` (or `short gate slot`) line in the log, and a short-lane
patch run past `short_seconds` adds an `overrun` line; the slot is held per run, so a gate can take it between two.
The test command gets `LOOP_GATE_SLOT_HELD=<lock path>`: a wrapper that takes the same lock runs its command without
taking it again, since it would otherwise wait on its own parent. A run already started under that variable naming
the slot takes no lock. There is no option to skip the slot.

The log: line 1 is `git rev-parse HEAD`, line 2 this command line, line 3 the lane and why (`short: head run 6.5 s ≤
120 s`, `heavy: head run 412.0 s > 120 s`, `heavy: head run failed (exit 1)`, `heavy: short_seconds is 0`, `heavy:
run under a holder of the heavy slot`), then `<patch>: exit <n> killed|survived|inconclusive: ...` per patch, then the head run's
output under `== head ==` and each patch's test output under a `== <patch> ==` header. It is rewritten after every
run, so a stopped run keeps what it finished. Exit 0 when every patch was killed, 1 when one survived (the log names it),
else 3 when one was inconclusive, 2 when it refuses, a patch doesn't apply, or the tree can't be restored (stderr names the paths). The log goes outside the
checkout or to an ignored path, never a tracked file or a patch, since writing it would destroy that file. Standard
library and git, and approvals.py, beside it, to read the policy and run each test command under the host's heavy wrapper (so PyYAML).
"""

from __future__ import annotations

import argparse
import fcntl
import glob
import hashlib
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


class Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        self.signum = signum


class Refused(Exception):
    pass


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def changes() -> str:
    """Every change in the checkout, empty when it is clean (approvals.py's `checkout_state`)."""
    # untracked files and submodule edits listed whatever status.showUntrackedFiles or submodule.*.ignore say
    status = git(
        "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"
    ).stdout
    # status skips files whose index flag says so (assume-unchanged, set by core.ignoreStat; skip-worktree)
    hidden = [
        f"{line[2:]} (index flag hides its changes)\n"
        for line in git("ls-files", "-v").stdout.splitlines()
        if line[:1].islower() or line[:1] == "S"
    ]
    return status + "".join(hidden)


def on_signal(signum: int, _frame: object) -> None:
    # a second signal while the patch is undone would leave it half applied
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise Interrupted(signum)


# the host's gate slots (SKILL.md, One heavy gate per host slot): the heavy ones, which approvals.py's take_slot picks
# from, and the short lane
SHORT = "gate.short.lock"
# the policy's `short_seconds` when it sets none
SHORT_SECONDS = 120
SLOT_HELD = "LOOP_GATE_SLOT_HELD"
# the policy's `mutate.inconclusive_exit` when it sets none: a test command's exit for "setup failed, no verdict"
# (EX_TEMPFAIL, sysexits.h), which no test runner reports for a failed assertion
INCONCLUSIVE_EXIT = 75


def slot_path(name: str = SHORT) -> str:
    """The short lane's lock file (a heavy slot is approvals.take_slot's to pick)."""
    return approvals().slot_file(name)


def approvals() -> Any:
    """approvals.py beside this script, which holds the policy's reader and the heavy-step runner."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import approvals as loaded

    return loaded


def policy() -> tuple[int, int]:
    """The policy's `short_seconds` (SKILL.md, Settings, SHORT_SECONDS without it) and `mutate.inconclusive_exit`
    (INCONCLUSIVE_EXIT without it); a policy off its schema is refused, as approvals.py refuses it, and so is a
    reserved exit outside 1..255, which no command can return or which would read a pass as a setup failure."""
    loaded = approvals()
    try:
        settings = loaded.settings(loaded.project()[1])
    except loaded.Refused as refusal:
        raise Refused(str(refusal)) from refusal
    reserved = settings.get("mutate", {}).get("inconclusive_exit", INCONCLUSIVE_EXIT)
    if not 1 <= reserved <= 255:
        raise Refused(
            f"`mutate.inconclusive_exit` is {reserved}: it must be a whole number from 1 to 255"
        )
    return settings.get("short_seconds", SHORT_SECONDS), reserved


def digest(paths: list[str], head: bool = False) -> str:
    """One hash over what `paths` (globs, relative to the working directory) name: a file's bytes, and for a directory
    every file under it by relative path and bytes, so a library beside an unchanged stub binary still changes it.
    A glob that names nothing is refused for the head run, since an empty comparison would call every patch not built;
    after a patch's run it only counts as a difference (that build removed its output), since the patch is applied."""
    whole = hashlib.sha256()
    for pattern in paths:
        found = sorted(glob.glob(pattern, recursive=True))
        if not found and head:
            raise Refused(f"--built {pattern} matches nothing after the head run")
        whole.update(f"pattern {pattern} {len(found)}\0".encode())
        for match in found:
            files = (
                sorted(
                    os.path.join(root, name) for root, _, names in os.walk(match) for name in names
                )
                if os.path.isdir(match)
                else [match]
            )
            for file in files:
                whole.update(file.encode() + b"\0")
                if os.path.islink(file):
                    whole.update(b"link " + os.readlink(file).encode())
                else:
                    with open(file, "rb") as handle:
                        for chunk in iter(lambda: handle.read(1 << 20), b""):
                            whole.update(chunk)
                whole.update(b"\0")
    return whole.hexdigest()


def take_short(path: str, waiting: Callable[[], None]) -> int | None:
    """Hold the short lane's exclusive flock and return its fd (closing it frees the lock, as does the process dying);
    None when this run already runs under a holder of that same path. `waiting` is called once, before blocking."""
    if os.environ.get(SLOT_HELD) == path:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            waiting()
            fcntl.flock(fd, fcntl.LOCK_EX)
    except BaseException:
        os.close(fd)
        raise
    return fd


def run_test(
    command: str, slot: str, waiting: Callable[[], None] = lambda: None
) -> tuple[int, str, float]:
    """The test command's exit code, output and seconds (the wait for the slot not counted), run under the gate slot
    whose lock file is `slot`, the short lane's, else the first free heavy slot (approvals.take_slot); on a signal its
    whole process group is stopped first."""
    if slot == slot_path(SHORT):
        fd = take_short(slot, waiting)
    else:
        fd, slot = approvals().take_slot(waiting)
    try:
        began = time.monotonic()
        code, output = run_command(command, slot)
        return code, output, time.monotonic() - began
    finally:
        if fd is not None:
            os.close(fd)


def lane(
    command: str, limit: int, waiting: Callable[[], None], built: bool = False
) -> tuple[str, str, str | None]:
    """The slot every patch's run takes, the log's line saying why, and the head run's output (None when none ran): the
    short lane when the test command passes on the unmutated head, in the short lane, within `limit` seconds. With
    `built` a head run is needed whatever the lane, since its outputs are what each patch's are compared to: one that
    would run none runs once in the heavy slot."""
    heavy = approvals().slot_path()
    # its holder is this run's parent: a short-lane run would hand its children a variable that no longer names the
    # heavy slot, and a heavy wrapper under them would wait on that parent
    if approvals().held_slot() is not None:
        why = "heavy: run under a holder of the heavy slot"
        return heavy, why, run_test(command, heavy, waiting)[1] if built else None
    if limit <= 0:
        why = f"heavy: short_seconds is {limit}"
        return heavy, why, run_test(command, heavy, waiting)[1] if built else None
    code, output, seconds = run_test(command, slot_path(SHORT), waiting)
    if code:
        return heavy, f"heavy: head run failed (exit {code})", output
    if seconds <= limit:
        return slot_path(SHORT), f"short: head run {seconds:.1f} s ≤ {limit} s", output
    return heavy, f"heavy: head run {seconds:.1f} s > {limit} s", output


def run_command(command: str, slot: str) -> tuple[int, str]:
    # a heavy step (approvals.run_heavy): the shell's argv as shell=True builds it, under the host's heavy wrapper, in a
    # session of its own, so stopping it (Interrupted) reaches every process the shell started
    return approvals().run_heavy(
        ["/bin/sh", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        # a test may print bytes that aren't UTF-8; strict decoding would raise with the patch still applied
        encoding="utf-8",
        errors="replace",
        # a .pyc written in the same second as its source hides the next same-sized patch of it
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", SLOT_HELD: slot},
    )


def restore(top: Path, patch: Path) -> None:
    """Undo `patch` when the tree shows it, then require a clean tree."""
    if changes():
        git("apply", "-R", str(patch), cwd=top)
    left = changes()
    if left:
        raise Refused(f"the tree could not be restored after {patch}:\n{left}")


def leave_own_environment() -> None:
    """Hand every command this script starts the caller's environment, not the script's own. uv puts the script's
    environment in VIRTUAL_ENV, its bin first on PATH and counts the run in UV_RUN_RECURSION_DEPTH, and a tool that
    follows VIRTUAL_ENV (a type checker) would check the project against the script's packages. A VIRTUAL_ENV equal
    to this script's own is dropped with its bin on PATH, and one that points elsewhere (the script started by an
    interpreter directly) is passed on unchanged; no value is reconstructed, so under `uv run`, which replaces the
    caller's VIRTUAL_ENV before the script starts, the caller's own value does not reach the commands."""
    own = os.path.normpath(sys.prefix)
    if os.path.normpath(os.environ.get("VIRTUAL_ENV", "\0")) != own:
        return
    del os.environ["VIRTUAL_ENV"]
    bin_dir = os.path.join(own, "bin")
    os.environ["PATH"] = os.pathsep.join(
        e for e in os.environ.get("PATH", "").split(os.pathsep) if os.path.normpath(e) != bin_dir
    )
    if (depth := os.environ.get("UV_RUN_RECURSION_DEPTH", "")).isdigit():
        if int(depth) > 1:
            os.environ["UV_RUN_RECURSION_DEPTH"] = str(int(depth) - 1)
        else:
            del os.environ["UV_RUN_RECURSION_DEPTH"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--test", required=True, help="the test command, run through the shell")
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument(
        "--built",
        action="append",
        default=[],
        metavar="PATH",
        help="what the test command builds from the code under test (repeatable, globs): a file, or a directory"
        " hashed over every file under it; a patch whose hash equals the head run's is inconclusive, not built",
    )
    parser.add_argument("patches", nargs="+", type=Path)
    args = parser.parse_args(argv)
    head = git("rev-parse", "HEAD")
    if head.returncode:
        print(f"mutate: not in a git checkout: {head.stderr.strip()}", file=sys.stderr)
        return 2
    top = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    # git apply run in a subdirectory skips paths outside it, so every apply runs at the top
    patches = [(name, name.resolve()) for name in args.patches]
    # the log is written before the tree is checked: a tracked file or a patch there would be lost to it
    where = args.log.resolve()
    if where in {path for _, path in patches} or (
        where.is_relative_to(top.resolve())
        and git("check-ignore", "-q", str(where), cwd=top).returncode
    ):
        print(
            f"mutate: the log {args.log} is a patch, or a path in the checkout that isn't ignored: write it under an"
            " ignored folder such as tmp/loop/, or outside the checkout",
            file=sys.stderr,
        )
        return 2
    lines = [head.stdout.strip(), shlex.join(sys.argv)]
    outputs: list[str] = []

    def write_log() -> None:
        args.log.write_text("\n".join(lines + outputs) + "\n")

    def refused(refusal: Refused) -> int:
        lines.append(f"refused: {str(refusal).splitlines()[0]}")
        write_log()
        print(f"mutate: {refusal}", file=sys.stderr)
        return 2

    write_log()
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    survived = inconclusive = False
    current: Path | None = None
    try:
        dirty = changes()
        if dirty:
            raise Refused(
                f"the tree has changes, so a restore could not tell them from a patch:\n{dirty.rstrip()}\n"
                "commit or stash them, then run mutate again"
            )
        for name, path in patches:
            check = git("apply", "--check", str(path), cwd=top)
            if check.returncode:
                raise Refused(f"{name} does not apply: {check.stderr.strip()}")
        limit, reserved = policy()

        def waiting(name: object, slot: str) -> Callable[[], None]:
            def said() -> None:
                lines.append(
                    f"{name}: waiting for the {'short' if slot == slot_path(SHORT) else 'host'} gate slot"
                )
                write_log()

            return said

        slot, why, head_output = lane(
            args.test, limit, waiting("head", slot_path(SHORT)), bool(args.built)
        )
        lines.append(why)
        if head_output is not None:
            outputs += ["", "== head ==", head_output.rstrip("\n")]
        write_log()
        # what the head run built, which a patch's run must differ from to have reached it
        built = digest(args.built, head=True) if args.built else None
        # a change the head run left would read as the first patch's own and fail its restore
        left = changes()
        if left:
            raise Refused(f"the head run left changes in the tree:\n{left}")
        for name, path in patches:
            current = path
            # applies: --check passed on this same tree, which restore() left clean
            git("apply", str(path), cwd=top)
            code, output, seconds = run_test(args.test, slot, waiting(name, slot))
            # a setup failure, or a build that left the output as the head's, says nothing about the patch
            if code == reserved:
                verdict = "inconclusive: setup failed, no verdict"
            elif built is not None and digest(args.built) == built:
                verdict = "not built: inconclusive"
            else:
                verdict = "survived" if code == 0 else "killed"
            survived |= verdict == "survived"
            inconclusive |= "inconclusive" in verdict
            # logged before the restore, so a restore that refuses keeps the result it followed
            lines.append(f"{name}: exit {code} {verdict}")
            if slot == slot_path(SHORT) and seconds > limit:
                lines.append(f"{name}: overrun: {seconds:.1f} s > {limit} s in the short lane")
            outputs += ["", f"== {name} ==", output.rstrip("\n")]
            write_log()
            restore(top, path)
            current = None
    except Interrupted as stop:
        if current:
            try:
                restore(top, current)
            except Refused as refusal:
                return refused(refusal)
        lines.append(f"stopped by {signal.Signals(stop.signum).name}")
        write_log()
        signal.signal(stop.signum, signal.SIG_DFL)
        os.kill(os.getpid(), stop.signum)
        return 128 + stop.signum
    except Refused as refusal:
        # nothing is applied here: git apply is all or nothing, and a failed restore names what it left
        return refused(refusal)
    except BaseException:
        # any other failure still undoes the applied patch, since the next gate or push runs in this tree
        if current:
            git("apply", "-R", str(current), cwd=top)
        raise
    return 1 if survived else 3 if inconclusive else 0


if __name__ == "__main__":
    leave_own_environment()  # before the test command starts
    sys.exit(main(sys.argv[1:]))
