#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Ruleset drift (engineering loop): commit what the repo's rulesets are meant to block, and notice when they stop.

    uv run scripts/rulesets.py snapshot [--repo OWNER/REPO]
    uv run scripts/rulesets.py check [--repo OWNER/REPO ...]

A ruleset with no bypass actors blocks force-pushes, deletions and direct pushes for everyone, admins included. Only
an edit of the ruleset itself gets past it, and GitHub sends no alert for one, so a project runs `check` on a schedule
(for example from its hygiene job).

- `snapshot` writes each live ruleset to `.github/rulesets/<name>.json` (spaces in the name become `-`) in the
  checkout, keeping only the fields that decide what it blocks: `name`, `target`, `enforcement`, `conditions`, `rules`
  and `bypass_actors`. A repo commits the result through a normal PR.
- `check` reads the expected files from each repo's default branch through the API, not the working tree, so it works
  from any checkout and a local edit can't hide drift, and compares them with the live rulesets. One line per
  difference, exit 1: a ruleset missing; enforcement not as expected; `conditions`, `target` changed; a rule removed,
  added or with other parameters; a bypass actor added or removed. Any difference counts, a stricter one included: an
  intended change lands as a PR that updates the file. Nothing differs: no output, exit 0. A repo with no
  `.github/rulesets/` is skipped with a note, not failed.

Without `--repo` both act on gh's default repo. Exit 1 with gh's reason on an API error. Stdlib, and PyYAML through approvals.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# importing approvals.py would cache its bytecode in the installed skill folder, an untracked change there
sys.dont_write_bytecode = True
from approvals import Refused, one_repo, toplevel

DIR = ".github/rulesets"
FIELDS = ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")
RAW = "Accept: application/vnd.github.raw+json"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def trimmed(ruleset: dict) -> dict:
    """The fields that decide what a ruleset blocks, rules sorted by type and an empty `parameters` dropped, so two
    spellings of one ruleset compare equal."""
    kept = {field: ruleset.get(field) for field in FIELDS}
    kept["conditions"] = kept["conditions"] or {}
    kept["bypass_actors"] = kept["bypass_actors"] or []
    kept["rules"] = sorted(
        ({k: v for k, v in rule.items() if k != "parameters" or v} for rule in kept["rules"] or []),
        key=lambda rule: rule["type"],
    )
    return kept


def dump(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def differences(want: dict, have: dict) -> list[str]:
    """One line per way `have` (live) differs from `want` (committed), both trimmed."""
    found = []
    if want["target"] != have["target"]:
        found.append(f"target is {have['target']}, expected {want['target']}")
    if have["enforcement"] != want["enforcement"] or have["enforcement"] != "active":
        found.append(f"enforcement is {have['enforcement']}, expected {want['enforcement']}")
    if want["conditions"] != have["conditions"]:
        found.append(
            f"conditions changed: {dump(have['conditions'])}, expected {dump(want['conditions'])}"
        )
    wanted_rules = {rule["type"]: rule for rule in want["rules"]}
    live_rules = {rule["type"]: rule for rule in have["rules"]}
    for kind in sorted(wanted_rules.keys() | live_rules.keys()):
        if kind not in live_rules:
            found.append(f"rule {kind} removed")
        elif kind not in wanted_rules:
            found.append(f"rule {kind} added")
        elif wanted_rules[kind] != live_rules[kind]:
            found.append(
                f"rule {kind} parameters changed: {dump(live_rules[kind].get('parameters'))},"
                f" expected {dump(wanted_rules[kind].get('parameters'))}"
            )
    wanted_bypass = {dump(actor) for actor in want["bypass_actors"]}
    live_bypass = {dump(actor) for actor in have["bypass_actors"]}
    found += [f"bypass actor added: {actor}" for actor in sorted(live_bypass - wanted_bypass)]
    found += [f"bypass actor removed: {actor}" for actor in sorted(wanted_bypass - live_bypass)]
    return found


def live(repo: str) -> list[dict]:
    listed = json.loads(gh("api", f"repos/{repo}/rulesets?per_page=100"))
    return [json.loads(gh("api", f"repos/{repo}/rulesets/{item['id']}")) for item in listed]


def default_repo() -> str:
    return gh(
        "api", "repos/{owner}/{repo}", "--jq", ".full_name"
    ).strip()  # REST: GraphQL is blocked in some sessions


def expected(repo: str) -> list[dict] | None:
    """The trimmed rulesets committed on the repo's default branch, or None when it has no `.github/rulesets/`."""
    try:
        listing = json.loads(gh("api", f"repos/{repo}/contents/{DIR}"))
    except subprocess.CalledProcessError as exc:
        if "404" in exc.stderr or "Not Found" in exc.stderr:
            return None
        raise
    return [
        trimmed(json.loads(gh("api", "-H", RAW, f"repos/{repo}/contents/{item['path']}")))
        for item in listing
        if item["name"].endswith(".json")
    ]


def check(repos: list[str]) -> int:
    drift = False
    for repo in repos:
        wanted = expected(repo)
        if wanted is None:
            print(f"{repo}: no {DIR}/ on its default branch, skipped")
            continue
        have = {ruleset["name"]: trimmed(ruleset) for ruleset in live(repo)}
        committed = {want["name"] for want in wanted}
        for name in sorted(have.keys() - committed):
            print(f"{repo}: ruleset {name} is not committed")
            drift = True
        for want in wanted:
            if want["name"] not in have:
                print(f"{repo}: ruleset {want['name']} is missing")
                drift = True
                continue
            for line in differences(want, have[want["name"]]):
                print(f"{repo}: ruleset {want['name']}: {line}")
                drift = True
    return 1 if drift else 0


def snapshot(repo: str) -> int:
    out = toplevel() / DIR
    out.mkdir(parents=True, exist_ok=True)
    for ruleset in live(repo):
        path = out / f"{ruleset['name'].replace(' ', '-')}.json"
        path.write_text(json.dumps(trimmed(ruleset), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(toplevel())}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot").add_argument("--repo")
    sub.add_parser("check").add_argument("--repo", action="append")
    args = parser.parse_args(argv)
    try:
        one_repo()
        if args.command == "snapshot":
            return snapshot(args.repo or default_repo())
        return check(args.repo or [default_repo()])
    except Refused as exc:
        print(exc)
        return 1
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
