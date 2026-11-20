#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Nightly (engineering-loop): a red nightly opens one issue listing the merges that could have caused it.

    uv run scripts/nightly.py red --last-green <sha> --red <sha> --run <url> [--repo <owner/name>] [--dry-run]

A project's nightly calls it when it ends red (SKILL.md, Nightly), from a checkout of the default branch holding the
history between the two commits (a shallow checkout fetches it first, such as `fetch-depth: 0`): `--last-green` is
the newest default-branch commit a nightly passed on, `--red` the one this run failed on, `--run` the run's link.

It walks the default branch's first-parent history from the last green commit (excluded) to the red one (included),
oldest first, and finds each commit's PR: a squash or `land` commit's subject ends `(#<n>)`, a merge commit's starts
`Merge pull request #<n>`, and any other commit asks GitHub which merged PR made it; a commit no PR made (a direct
push) is listed as a commit. Each PR is shown with the issues its body links (a closing keyword, `Part of` or
`Implements` before `#<n>`, as the gatekeeper reads them) and each issue's epic (its parent issue).

Then, unless an open issue titled `Nightly red since <the last green's first 7 hex digits>` exists, it opens one with
that title, the run's link and the list; while that issue is open it comments on it instead, with the new run's link
and only the merges since the red commit its last post names, so each red night adds what is new and a person or a
lead bisects from the issue. Every post carries a hidden line `<!-- nightly-red last-green=<sha> red=<sha> -->`, which
the next run reads to find where the new merges start.

Every body is checked first against the local deny list, the file the environment variable `LOOP_DENY_LIST` names
(one term per line, `#` starts a comment, matched ignoring case at word boundaries): a line naming a term refuses the
post before any call to GitHub, since a public repo keeps an issue's first text in its edit history. A list the
variable names that can't be read refuses too. `--dry-run` prints the body it would post and posts nothing.

The repository is `--repo`, else `GITHUB_REPOSITORY` (set in GitHub Actions), else the `origin` remote's GitHub slug.
It needs only git and gh (REST calls through `gh api`, so a token that may read pull requests and write issues).

On success it prints the issue's or the comment's URL. Exit codes: 0 posted (or printed, with `--dry-run`, which still reads GitHub to choose between issue and comment); 1 refused
by the deny list, or a gh call failed; 2 a usage error, a commit git can't find, or a last green commit that is not an
ancestor of the red one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# importing folding.py would cache its bytecode in the installed skill folder, an untracked change there
sys.dont_write_bytecode = True
from folding import fold

# the environment variable naming the local deny list, a file kept outside the repo (gatekeeper.py's DENY_LIST)
DENY_LIST = "LOOP_DENY_LIST"
TITLE = "Nightly red since {}"
SHORT = 7
MARKER = "<!-- nightly-red last-green={} red={} -->"
MARKED = re.compile(r"<!-- nightly-red last-green=([0-9a-f]{7,64}) red=([0-9a-f]{7,64}) -->")
# a squash commit's or land's subject: `<title> (#<n>)`; a merge commit's: `Merge pull request #<n> from ...`
SQUASHED = re.compile(r"\(#(\d+)\)\s*$")
MERGED = re.compile(r"^Merge pull request #(\d+)\b")
# the gatekeeper's links: GitHub's closing keywords, `Part of` and `Implements`, outside code and comments
LINKED = re.compile(
    r"\b(?:(close[sd]?|fix(?:e[sd])?|resolve[sd]?)|(part[ \t]+of)|(implements)):?[ \t]+#(\d+)\b",
    re.IGNORECASE,
)
QUOTED = re.compile(r"^[ \t>]*```.*?^[ \t>]*```|`[^`\n]*`|<!--.*?-->", re.DOTALL | re.MULTILINE)
REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")
PAGE = 100


class Refused(Exception):
    """A post refused, or a call that failed: the message says why, and nothing was posted."""


class Usage(Exception):
    """A usage or git error: exit 2."""


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise Usage(f"git {' '.join(args)}: {result.stderr.strip() or f'exit {result.returncode}'}")
    return result.stdout


def gh(*args: str) -> Any:
    """One `gh api` call, its JSON answer parsed."""
    result = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise Refused(
            f"gh api {' '.join(args)}: {result.stderr.strip() or f'exit {result.returncode}'}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else None


def denied(text: str) -> None:
    """Refuse `text` when a line names a term of the deny list `LOOP_DENY_LIST` names; without it, check nothing."""
    where = os.environ.get(DENY_LIST)
    if not where:
        return
    try:
        listed = Path(where).expanduser().read_text().splitlines()
    except OSError as exc:
        raise Refused(
            f"{DENY_LIST} names {where}, which can't be read ({exc.strerror}): nothing posted"
        ) from exc
    terms = [term for term in (line.split("#", 1)[0].strip() for line in listed) if term]
    for number, line in enumerate(text.splitlines(), 1):
        for term in terms:
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", line, re.IGNORECASE):
                raise Refused(
                    f"refused to post: line {number} names `{term}` from the deny list ({DENY_LIST}); nothing posted"
                )


def repository(given: str | None) -> str:
    if given:
        return given
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    found = REMOTE.search(git("remote", "get-url", "origin").strip())
    if not found:
        raise Usage(
            "no --repo, no GITHUB_REPOSITORY, and the origin remote is not a GitHub repository"
        )
    return found.group(1)


def commit(ref: str) -> str:
    try:
        return git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()
    except Usage:
        raise Usage(
            f"no commit {ref} in this checkout (a shallow one fetches the history first)"
        ) from None


def ancestor(older: str, newer: str) -> bool:
    return (
        subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], check=False).returncode
        == 0
    )


def commits(since: str, until: str) -> list[tuple[str, str, int]]:
    """The first-parent commits after `since` up to `until`, oldest first: (sha, subject, parent count)."""
    out = git("log", "--first-parent", "--reverse", "--format=%H%x00%P%x00%s", f"{since}..{until}")
    rows = []
    for line in out.splitlines():
        sha, parents, subject = line.split("\x00", 2)
        rows.append((sha, subject, len(parents.split())))
    return rows


def links(body: str) -> list[tuple[int, str]]:
    """The issues a PR body links, in order, each once with its kind; a closing keyword wins, then `Implements`."""
    rank = ("closes", "implements", "part of")
    found: dict[int, str] = {}
    for closes, part, implements, number in LINKED.findall(QUOTED.sub("", body or "")):
        kind = "closes" if closes else "implements" if implements else "part of"
        found[int(number)] = min(found.get(int(number), kind), kind, key=rank.index)
    return list(found.items())


class GitHub:
    """The REST reads and writes, each issue and PR read once."""

    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.issues: dict[int, dict[str, Any]] = {}

    def issue(self, number: int) -> dict[str, Any]:
        if number not in self.issues:
            self.issues[number] = gh(f"repos/{self.repo}/issues/{number}")
        return self.issues[number]

    def epic(self, number: int) -> dict[str, Any] | None:
        if not self.issue(number).get("parent_issue_url"):
            return None
        parent = gh(f"repos/{self.repo}/issues/{number}/parent")
        self.issues.setdefault(parent["number"], parent)
        return parent

    def pull(self, number: int) -> dict[str, Any]:
        return gh(f"repos/{self.repo}/pulls/{number}")

    def made(self, sha: str) -> int | None:
        """The PR whose merge made commit `sha`, by GitHub's commit-to-PR lookup."""
        for pull in gh(f"repos/{self.repo}/commits/{sha}/pulls") or []:
            if pull.get("merge_commit_sha") == sha:
                return int(pull["number"])
        return None

    def open_issue(self, title: str) -> dict[str, Any] | None:
        page = 1
        while True:
            found = (
                gh(
                    "-X",
                    "GET",
                    f"repos/{self.repo}/issues",
                    "-f",
                    "state=open",
                    "-f",
                    f"per_page={PAGE}",
                    "-f",
                    f"page={page}",
                )
                or []
            )
            for issue in found:
                if issue.get("title") == title and "pull_request" not in issue:
                    return issue
            if len(found) < PAGE:
                return None
            page += 1

    def comments(self, number: int) -> list[dict[str, Any]]:
        page, every = 1, []
        while True:
            found = (
                gh(
                    "-X",
                    "GET",
                    f"repos/{self.repo}/issues/{number}/comments",
                    "-f",
                    f"per_page={PAGE}",
                    "-f",
                    f"page={page}",
                )
                or []
            )
            every += found
            if len(found) < PAGE:
                return every
            page += 1

    def post(self, path: str, payload: dict[str, str]) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
        try:
            return gh(f"repos/{self.repo}/{path}", "--input", handle.name)
        finally:
            os.unlink(handle.name)


def line(hub: GitHub, sha: str, subject: str, parents: int) -> str:
    """One commit's line: its PR with the issues it links and their epics, or the bare commit."""
    short = sha[:SHORT]
    found = SQUASHED.search(subject) or MERGED.match(subject)
    number = int(found.group(1)) if found else hub.made(sha)
    if number is None:
        return f"- `{short}` {subject} (no PR: a direct push)"
    pull = hub.pull(number)
    how = "merge" if parents > 1 else "squash"
    text = f"- #{number} {pull.get('title', '')} ({how} `{short}`)"
    linked = []
    for issue, kind in links(pull.get("body") or ""):
        if "pull_request" in hub.issue(issue):
            continue
        epic = hub.epic(issue)
        linked.append(f"{kind} #{issue}" + (f", epic #{epic['number']}" if epic else ""))
    return text + (": " + "; ".join(linked) if linked else ": links no issue")


def listing(hub: GitHub, since: str, until: str) -> list[str]:
    return [line(hub, sha, subject, parents) for sha, subject, parents in commits(since, until)]


def red(args: argparse.Namespace) -> int:
    green, failed = commit(args.last_green), commit(args.red)
    if not ancestor(green, failed):
        raise Usage(
            f"the last green {green[:SHORT]} is not an ancestor of the red {failed[:SHORT]}"
        )
    hub = GitHub(repository(args.repo))
    title = TITLE.format(green[:SHORT])
    existing = hub.open_issue(title)
    marker = MARKER.format(green, failed)
    if existing is None:
        lines = listing(hub, green, failed) or ["- none: the red commit is the last green one"]
        body = (
            fold(
                f"The nightly is red since `{green[:SHORT]}`, its last green commit; "
                + f"it failed on `{failed[:SHORT]}`: {args.run}",
                details="Merged on the default branch since the last green, oldest first; bisect from these:\n\n"
                + "\n".join(lines),
            )
            + f"\n{marker}"
        )
    else:
        posts = [existing.get("body") or ""] + [
            c.get("body") or "" for c in hub.comments(existing["number"])
        ]
        reds = [m.group(2) for post in posts for m in MARKED.finditer(post)]
        since = next((sha for sha in reversed(reds) if ancestor(sha, failed)), green)
        lines = listing(hub, since, failed) or [
            f"- none since `{since[:SHORT]}`, the red commit the last post names"
        ]
        body = (
            fold(
                f"Still red on `{failed[:SHORT]}`: {args.run}",
                details=f"Merged since `{since[:SHORT]}`, oldest first:\n\n" + "\n".join(lines),
            )
            + f"\n{marker}"
        )
    denied(body)
    if args.dry_run:
        print(body)
        return 0
    if existing is None:
        made = hub.post("issues", {"title": title, "body": body})
    else:
        made = hub.post(f"issues/{existing['number']}/comments", {"body": body})
    print(made.get("html_url", ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nightly: open or extend the issue of a red nightly."
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    verb = verbs.add_parser(
        "red", help="list the merges since the last green commit on the nightly's issue"
    )
    verb.add_argument(
        "--last-green", required=True, help="the newest default-branch commit a nightly passed on"
    )
    verb.add_argument("--red", required=True, help="the commit this nightly failed on")
    verb.add_argument("--run", required=True, help="the nightly run's link")
    verb.add_argument(
        "--repo", help="owner/name; default GITHUB_REPOSITORY, else the origin remote"
    )
    verb.add_argument("--dry-run", action="store_true", help="print the body, post nothing")
    args = parser.parse_args(argv)
    try:
        return red(args)
    except Usage as exc:
        print(f"nightly: {exc}", file=sys.stderr)
        return 2
    except Refused as exc:
        print(f"nightly: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
