#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Acceptance checks (engineering-loop): run one spec's checks from a folder of executables.

    uv run scripts/acceptance.py <issue>
    uv run scripts/acceptance.py --all

The fallback for a project whose `docs/agents/loop.md` has no `Acceptance tests: <command>` line
(SKILL.md, Acceptance checks). It runs every executable file in `acceptance/<issue>/` at the repo
root (the top of the git checkout it is run in, else the current directory), in name order, each
from the repo root with no input: a shell script, a SQL client call, an HTTP call, any language,
since the runner reads only each file's exit code. A non-executable file (a fixture, a README) and
a subfolder are not checks and are skipped. Each check's own output passes through, then one line:

    PASS acceptance/7/01-ok.sh (0.1s)
    FAIL acceptance/7/02-broken.sh (2.3s)

A file that cannot be started (no shebang, say) is a FAIL with the reason. `--all` runs every
`acceptance/*/` folder in issue order, for the nightly. The last line is the total:
`TOTAL <n> checks, <passed> passed, <failed> failed (<s>s)`.

The budget: one spec's run should finish within 10 min and the `--all` run within 90 min, or the
minutes loop.md sets with `Acceptance budget: <spec minutes>, <nightly minutes>`. Over it, one more
line says so (`OVER BUDGET ...`) and the exit code is still the checks' own, since the budget is a
signal to split a slow check or move it to the nightly, not a gate. A malformed budget line is
reported and the defaults apply.

Exit codes: 0 every check passed; 1 a check failed; 2 nothing to run (the folder is missing or holds
no executable file, or under `--all` no folder does, or one folder holds none and nothing failed),
so "no checks" is never read as "passed"; a usage error also exits 2.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

FOLDER = "acceptance"
LOOP_MD = Path("docs") / "agents" / "loop.md"
DEFAULT_BUDGET = (10.0, 90.0)  # minutes: one spec's run, the --all run
BUDGET_LINE = re.compile(r"^\W*Acceptance budget:\s*(.*?)\W*$", re.MULTILINE)
BUDGET_VALUE = re.compile(r"^(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)$")


def repo_root() -> Path:
    """The top of the git checkout the command runs in, else the current directory."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd()
    return Path(out) if out else Path.cwd()


def budget(root: Path) -> tuple[float, float]:
    """The (spec, nightly) minutes loop.md sets with `Acceptance budget:`, else the defaults."""
    path = root / LOOP_MD
    if not path.is_file():
        return DEFAULT_BUDGET
    found = BUDGET_LINE.search(path.read_text(errors="replace"))
    if not found:
        return DEFAULT_BUDGET
    value = BUDGET_VALUE.match(found.group(1).strip("` "))
    if not value:
        print(
            f"acceptance: {LOOP_MD}: `Acceptance budget: {found.group(1)}` is not "
            "`<spec minutes>, <nightly minutes>`; using 10, 90",
            file=sys.stderr,
        )
        return DEFAULT_BUDGET
    return float(value.group(1)), float(value.group(2))


def checks(folder: Path) -> list[Path]:
    """Every executable regular file directly in `folder`, in name order."""
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and os.access(p, os.X_OK)),
        key=lambda p: p.name,
    )


def issue_order(folder: Path) -> tuple[int, int, str]:
    """Numbered folders first, by number, then any other by name."""
    name = folder.name
    return (0, int(name), name) if name.isdigit() else (1, 0, name)


def run(check: Path, root: Path) -> bool:
    """Run one check from the repo root and print its PASS or FAIL line."""
    shown = check.relative_to(root).as_posix()
    sys.stdout.flush()
    started = time.monotonic()
    try:
        code = subprocess.run(
            [str(check)], cwd=root, stdin=subprocess.DEVNULL, check=False
        ).returncode
        reason = "" if code == 0 else f", exit {code}"
    except OSError as error:
        code, reason = -1, f", not started: {error.strerror or error}"
    seconds = time.monotonic() - started
    print(f"{'PASS' if code == 0 else 'FAIL'} {shown} ({seconds:.1f}s{reason})", flush=True)
    return code == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a spec's acceptance checks: every executable in acceptance/<issue>/."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("issue", nargs="?", help="the spec's issue number")
    target.add_argument("--all", action="store_true", help="every acceptance/*/ folder")
    args = parser.parse_args(argv)

    root = repo_root()
    base = root / FOLDER
    if args.all:
        folders = (
            sorted((p for p in base.iterdir() if p.is_dir()), key=issue_order)
            if base.is_dir()
            else []
        )
        if not folders:
            print(
                f"acceptance: no folder under {FOLDER}/, so there is nothing to run",
                file=sys.stderr,
            )
            return 2
    else:
        issue = args.issue.lstrip("#")
        if not issue.isdigit():
            parser.error(f"the issue is a number, not {args.issue!r}")
        folders = [base / issue]
        if not folders[0].is_dir():
            print(
                f"acceptance: {FOLDER}/{issue}/ does not exist, so there is nothing to run",
                file=sys.stderr,
            )
            return 2

    started = time.monotonic()
    passed = failed = 0
    empty = []
    for folder in folders:
        found = checks(folder)
        if not found:
            empty.append(folder)
            print(f"NONE {folder.relative_to(root).as_posix()}/ (no executable file)", flush=True)
        for check in found:
            if run(check, root):
                passed += 1
            else:
                failed += 1
    seconds = time.monotonic() - started

    print(f"TOTAL {passed + failed} checks, {passed} passed, {failed} failed ({seconds:.1f}s)")
    spec_minutes, nightly_minutes = budget(root)
    minutes = nightly_minutes if args.all else spec_minutes
    if seconds > minutes * 60:
        kind = "nightly" if args.all else "spec"
        print(
            f"OVER BUDGET {seconds:.1f}s > {minutes:g} min, the {kind} budget: split the slow "
            "check or move it to the nightly (a signal, not a gate)"
        )
    if failed:
        return 1
    if empty:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
