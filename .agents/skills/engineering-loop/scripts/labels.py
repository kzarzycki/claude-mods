#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Label sync (engineering loop): make the repo's labels the loop's fixed set plus docs/agents/issue-tracker.md's.

    uv run scripts/labels.py [--dry-run]

Run in the project's checkout, from the installed engineering-loop skill, `--dry-run` first. The project's
`mise run setup:github` runs it too. One line per change, then one per label it keeps:

- Renames first, in place (`PATCH labels/<old>`), so every open and closed issue and PR keeps its label: the
  tracker's `renames` (`old: new`), then the loop's own (`bug`, `enhancement` and `chore` to their `kind:` names,
  `documentation` to `kind:documentation`), then each component's and extra category's bare name to its `area:` or
  `kind:` label. Dependabot's labels are never renamed or folded. A rename whose new name already exists is a fold: each issue or PR with the old label gets the new
  one and loses the old, then the old is deleted. An old name the repo lacks is skipped, so the map can stay.
- Then it creates every listed label it lacks and updates one whose colour or description differs. A tracker name's
  description is its value, cut to GitHub's 100 characters.
- Then each unlisted label: deleted when no issue or PR, open or closed, carries it, else kept and reported with its
  count, since deleting it would lose who had it. A label whose name has a comma is kept and reported, never
  deleted or folded, since its carriers can't be counted. Dependabot's are kept, since it recreates them and its PRs use them.

A second run changes nothing. `--dry-run` reads the same and writes nothing. Without docs/agents/issue-tracker.md it
refuses, since nothing would say which labels are the repo's. Exit 1 with gh's reason. Stdlib, and PyYAML through approvals.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from urllib.parse import quote

# importing approvals.py would cache its bytecode in the installed skill folder, an untracked change there
sys.dont_write_bytecode = True
from approvals import (  # the label names, defined once
    BUG,
    EPIC,
    MERGE_LABEL,
    NEEDS_OWNER,
    POINTS,
    QUEUED,
    READY,
    RISK_LABEL,
    SIZE_ORDER,
    TRACKER,
    Refused,
    one_repo,
    qualified,
    read,
    toplevel,
    tracker_settings,
)

# the loop's fixed set (issues.md, Labels): name -> (colour, description)
LOOP_LABELS = {
    NEEDS_OWNER: (
        "d93f0b",
        "Waits for the owner: a decision, a step only they can take, or an approval",
    ),
    READY: ("0e8a16", "Ready: the spec is approved"),
    **{
        f"approved:{point}": ("0e8a16", f"The {point} is approved")
        for point in POINTS
        if f"approved:{point}" != READY
    },
    MERGE_LABEL: ("0e8a16", "The owner's merge approval of a high-risk PR"),
    RISK_LABEL: ("b60205", "Its consequences need the owner at merge"),
    QUEUED: (
        "fbca04",
        "land put it in GitHub's merge queue; off once its Landed comment is written or it merged elsewhere",
    ),
    EPIC: ("8250df", "An outcome the owner tracks; its work items are sub-issues"),
    BUG: ("d73a4a", "Something a user or the pipeline hits is wrong"),
    "kind:enhancement": ("a2eeef", "New or improved behaviour"),
    "kind:chore": ("c5def5", "Tooling, CI or agent configuration; no behaviour changes"),
    "kind:documentation": ("0075ca", "Docs only; no behaviour changes"),
    "size:XS": ("ededed", "One line or one config value"),
    "size:S": ("ededed", "One module"),
    "size:M": ("ededed", "Several modules"),
    "size:L": ("ededed", "Several workers or slices in one PR"),
    "size:XL": ("ededed", "Too big for one spec: split it"),
}
assert set(SIZE_ORDER) <= set(LOOP_LABELS)
# the loop's renames, after the tracker's own, so a project can send `documentation` elsewhere first
LOOP_RENAMES = [
    ("bug", BUG),
    ("enhancement", "kind:enhancement"),
    ("chore", "kind:chore"),
    ("documentation", "kind:documentation"),
]
AREA, KIND, EXTRA = "1d76db", "c5def5", "ededed"


def described(text: str) -> str:
    return text.replace("**", "").replace("`", "")[:100].rstrip()


def wanted(tracker: str) -> dict[str, tuple[str, str]]:
    """Every listed label: the loop's, the tracker's components (`area:`), extra categories (`kind:`) and extra
    labels, each with its colour and description."""
    found, tracked = dict(LOOP_LABELS), tracker_settings(tracker)
    for section, kind, colour in (
        ("components", "component", AREA),
        ("categories", "category", KIND),
    ):
        for name, text in tracked.get(section, {}).items():
            found[qualified(kind, name)] = (colour, described(text))
    for name, text in tracked.get("labels", {}).items():
        found.setdefault(name, (EXTRA, described(text)))
    return found


def renames(tracker: str) -> list[tuple[str, str]]:
    """Old name to new, in order: the tracker's `renames`, the loop's, then each component's and extra category's
    bare name to its label."""
    tracked = tracker_settings(tracker)
    mapped = list(tracked.get("renames", {}).items())
    bare = [
        (name, qualified(kind, name))
        for section, kind in (("components", "component"), ("categories", "category"))
        for name in tracked.get(section, {})
    ]
    return [(old, new) for old, new in [*mapped, *LOOP_RENAMES, *bare] if old != new]


def dependabot(name: str, description: str) -> bool:
    """Dependabot's own labels: `dependencies` and the ecosystem labels it describes as `Pull requests that update
    ...`. ponytail: its defaults only; read `.github/dependabot.yml`'s `labels:` when a repo sets its own and none
    of its PRs carries them yet."""
    return name == "dependencies" or description.startswith("Pull requests that update")


Action = tuple[str, str, str, str]  # (verb, name, new name or colour, description)


def plan(existing: dict[str, tuple[str, str]], tracker: str) -> tuple[list[Action], list[str]]:
    """The renames, folds, creations and updates that make `existing` (name -> colour, description) the listed set,
    and the unlisted labels left after them, which sync() deletes only when nothing carries them."""
    labels, actions = dict(existing), []
    for old, new in renames(tracker):
        # Dependabot's own label stays as it is, even when a component shares its name (`python`): that gets a new label
        if old not in labels or dependabot(old, labels[old][1]):
            continue
        actions.append(("fold" if new in labels else "rename", old, new, ""))
        kept = labels.pop(old)
        labels.setdefault(new, kept)
    for name, (colour, description) in wanted(tracker).items():
        if name not in labels:
            actions.append(("create", name, colour, description))
        elif labels[name] != (colour, description):
            actions.append(("update", name, colour, description))
    listed = wanted(tracker)
    unlisted = sorted(
        name
        for name, (_, text) in labels.items()
        if name not in listed and not dependabot(name, text)
    )
    return actions, unlisted


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def existing() -> dict[str, tuple[str, str]]:
    out = gh("api", "--paginate", "repos/{owner}/{repo}/labels?per_page=100", "--jq", ".[]")
    found = [json.loads(line) for line in out.splitlines()]
    return {
        label["name"]: (label["color"].lower(), label.get("description") or "") for label in found
    }


def carriers(name: str) -> list[int]:
    """Every issue and PR, open or closed, that carries the label. A name with a comma can't be asked for, since
    GitHub reads the filter as a list of labels an issue must all carry, so sync() keeps such a label (UNCOUNTED)."""
    out = gh(
        "api",
        "--paginate",
        "-X",
        "GET",
        "repos/{owner}/{repo}/issues",
        "-f",
        f"labels={name}",
        "-f",
        "state=all",
        "-f",
        "per_page=100",
        "--jq",
        ".[].number",
    )
    return [int(number) for number in out.split()]


# ponytail: a name with a comma is kept, never counted; count it with GraphQL `label(name:) { issues { totalCount } }`
# (and `pullRequests`) if a repo needs one deleted or folded
UNCOUNTED = "a name with a comma can't be counted, so it may be in use"


def labelled(name: str) -> str:
    return f"repos/{{owner}}/{{repo}}/labels/{quote(name, safe='')}"


def sync(dry_run: bool) -> int:
    root = toplevel()
    if not (root / TRACKER).exists():
        raise Refused(f"no {TRACKER}: nothing says which labels are the repo's")
    actions, unlisted = plan(existing(), read(root / TRACKER))
    would = "would " if dry_run else ""
    for verb, name, value, description in actions:
        if verb == "rename":
            if not dry_run:
                gh("api", "-X", "PATCH", labelled(name), "-f", f"new_name={value}", "--silent")
            print(f"{would}rename {name} to {value}")
        elif verb == "fold" and "," in name:
            print(f"kept {name}: {UNCOUNTED}; fold it into {value} by hand")
        elif verb == "fold":
            numbers = carriers(name)
            if not dry_run:
                for number in numbers:
                    path = f"repos/{{owner}}/{{repo}}/issues/{number}/labels"
                    gh("api", path, "-f", f"labels[]={value}", "--silent")
                    gh("api", "-X", "DELETE", f"{path}/{quote(name, safe='')}", "--silent")
                gh("api", "-X", "DELETE", labelled(name), "--silent")
            print(f"{would}fold {name} into {value} on {len(numbers)} issue(s) or PR(s)")
        else:
            if not dry_run:
                fields = ["-f", f"color={value}", "-f", f"description={description}", "--silent"]
                if verb == "create":
                    gh("api", "repos/{owner}/{repo}/labels", "-f", f"name={name}", *fields)
                else:
                    gh("api", "-X", "PATCH", labelled(name), *fields)
            print(f"{would}{verb} {name}")
    for name in unlisted:
        if "," in name:
            print(f"kept {name}: {UNCOUNTED}")
            continue
        numbers = carriers(name)
        if numbers:
            print(f"kept {name}: {len(numbers)} issue(s) or PR(s) carry it")
            continue
        if not dry_run:
            gh("api", "-X", "DELETE", labelled(name), "--silent")
        print(f"{would}delete {name}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        one_repo()
        return sync(args.dry_run)
    except Refused as exc:
        print(exc)
        return 1
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
