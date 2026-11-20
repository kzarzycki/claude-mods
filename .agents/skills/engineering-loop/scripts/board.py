#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Board move (engineering loop): put an issue in a column of the repo's project board.

    uv run scripts/board.py <issue> <column>
    uv run scripts/board.py column <issue>
    uv run scripts/board.py field <issue or PR> <field> <option>

The columns are the loop's stages (the skill's issues.md, Board), each shown in the board column of its own name unless
the `board` section of docs/agents/issue-tracker.md's settings block maps it to another, one key per loop column
(`Build = "In progress"`), several loop columns to one board column allowed. A name that is
no loop column is taken as a board column. Adds the issue to the board when it is not there yet,
then sets its Status. Ids are looked up by name on every call: GitHub changes option ids whenever a field is edited.
Exit 1 with gh's reason or the valid columns; the labels, not the board, are an issue's state, so a failed move never
blocks a ticket. Needs the `project` token scope (`gh auth refresh -s project`).

`column` prints the loop's column: the later of the one its board column shows (the earliest loop column mapped to it) and the one its labels give (issues.md, Board:
`needs-owner` is `Needs owner`, `approved:spec` is `Ready`, neither is `Intent`), since the labels are the state and a
board move may have failed. A board column no loop column maps to and the loop does not name is printed as is. `Sign-off` is a landed change
whose issue stays open for the owner's check in use (`Implements #n`), so it comes after `Verify` and before `Done`.

`field` sets another single-select field of an issue's or PR's item the same way, by the field's and the option's
names (`field 12 Risk High`): the board template's `Risk` holds a PR's risk beside its `risk:high` label.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

# importing approvals.py would cache its bytecode in the installed skill folder, an untracked change there
sys.dont_write_bytecode = True
# the label names and the docs' reading, defined once
from approvals import (
    NEEDS_OWNER,
    READY,
    TRACKER,
    Refused,
    one_repo,
    read,
    toplevel,
    tracker_settings,
)

# ponytail: the repo's first linked project is the board; pick by title when a second one is linked.
# an issue's or a PR's id and its items' value of the field, beside the board's field
ITEM = """id projectItems(first: 20) { nodes { project { id } fieldValueByName(name: $field) { ... on ProjectV2ItemFieldSingleSelectValue { name } } } }"""
LOOKUP = f"""query($owner: String!, $name: String!, $issue: Int!, $field: String!) {{
  repository(owner: $owner, name: $name) {{
    issueOrPullRequest(number: $issue) {{ ... on Issue {{ {ITEM} }} ... on PullRequest {{ {ITEM} }} }}
    projectsV2(first: 1) {{ nodes {{ id field(name: $field) {{ ... on ProjectV2SingleSelectField {{ id options {{ id name }} }} }} }} }}
  }}
}}"""
ADD = """mutation($project: ID!, $issue: ID!) {
  addProjectV2ItemById(input: {projectId: $project, contentId: $issue}) { item { id } }
}"""
COLUMN = """query($owner: String!, $name: String!, $issue: Int!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 1) { nodes { id } }
    issue(number: $issue) { labels(first: 50) { nodes { name } } projectItems(first: 20) { nodes { project { id } fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } } }
  }
}"""
SET = """mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
  updateProjectV2ItemFieldValue(input: {projectId: $project, itemId: $item, fieldId: $field, value: {singleSelectOptionId: $option}}) { projectV2Item { id } }
}"""


def target(
    projects: list[dict[str, Any]], column: str, field: str = "Status"
) -> tuple[str, str, str]:
    """The board's project id, the field's id and the option's id; the field is Status, whose options are columns."""
    if not projects:
        raise ValueError("no project board is linked to this repo")
    project = projects[0]
    options = {
        option["name"]: option["id"] for option in (project["field"] or {}).get("options", [])
    }
    if column not in options:
        kind = "column" if field == "Status" else f"{field} option"
        raise ValueError(
            f"no {kind} {column!r}: the board has {', '.join(options) or f'no {field} field'}"
        )
    return project["id"], project["field"]["id"], options[column]


def fields(**values: int | str) -> list[str]:
    """gh's field flags: -F for a number or a {placeholder} gh fills, -f for an id, which -F would turn into a number when it is all digits."""
    return [
        arg
        for key, value in values.items()
        for arg in (
            "-F" if isinstance(value, int) or value.startswith("{") else "-f",
            f"{key}={value}",
        )
    ]


def _graphql(query: str, **values: int | str) -> Any:
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}", *fields(**values)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)["data"]


def lookup(issue: int, field: str) -> dict[str, Any]:
    """The repo's board with the field, and the issue or PR with its items' value of it."""
    # gh fills owner and repo from the checkout
    return _graphql(LOOKUP, owner="{owner}", name="{repo}", issue=issue, field=field)["repository"]


def value(repo: dict[str, Any], field: str) -> str | None:
    """The field's option on the item of the repo's board (lookup()), None when it is off the board or unset; raises
    ValueError without a board or that field, as set_field() would."""
    boards = repo["projectsV2"]["nodes"]
    if not boards:
        raise ValueError("no project board is linked to this repo")
    if not boards[0]["field"]:
        raise ValueError(f"the board has no {field} field")
    return next(
        (
            (item["fieldValueByName"] or {}).get("name")
            for item in repo["issueOrPullRequest"]["projectItems"]["nodes"]
            if item["project"]["id"] == boards[0]["id"]
        ),
        None,
    )


def set_field(issue: int, field: str, option: str, repo: dict[str, Any] | None = None) -> None:
    """Set the single-select field of the issue's or PR's item to the option, adding it to the board first;
    `repo` is a lookup() already made."""
    repo = repo or lookup(issue, field)
    project, field_id, option_id = target(repo["projectsV2"]["nodes"], option, field)
    # the existing item when already there
    added = _graphql(ADD, project=project, issue=repo["issueOrPullRequest"]["id"])
    item = added["addProjectV2ItemById"]["item"]["id"]
    _graphql(SET, project=project, item=item, field=field_id, option=option_id)


def move(issue: int, column: str) -> None:
    """Set the issue's board column, a board column name (main maps the loop's)."""
    set_field(issue, "Status", column)


# the loop's columns in stage order (issues.md, Board)
COLUMNS = ["Intent", "Needs owner", "Ready", "Build", "Verify", "Sign-off", "Done"]


def mapping(tracker: str | None) -> dict[str, str]:
    """The board column of each loop column docs/agents/issue-tracker.md's `board` names; a loop column it does not
    name keeps its own name (callers use `.get(name, name)`)."""
    return tracker_settings(tracker).get("board", {}) if tracker else {}


def tracker_file() -> str | None:
    path = toplevel() / TRACKER
    return read(path) if path.exists() else None


def labelled(labels: set[str]) -> str:
    """The column an issue's state labels give."""
    return "Needs owner" if NEEDS_OWNER in labels else "Ready" if READY in labels else "Intent"


def column_of(repo: dict[str, Any], mapped: dict[str, str] | None = None) -> str:
    """The later of the loop column the issue's Status on the repo's board shows and the one its labels give. A board
    column several loop columns share shows the earliest of them; a Status no loop column maps to (`mapped`, mapping())
    and the loop does not name wins."""
    boards = repo["projectsV2"]["nodes"]
    status = next(
        (
            (item["fieldValueByName"] or {}).get("name", "")
            for item in repo["issue"]["projectItems"]["nodes"]
            if boards and item["project"]["id"] == boards[0]["id"]
        ),
        "",
    )
    labels = labelled({label["name"] for label in repo["issue"]["labels"]["nodes"]})
    mapped = mapped or {}
    shown = [column for column in COLUMNS if mapped.get(column, column) == status]
    if status and not shown:
        return status
    return max(shown[0] if shown else labels, labels, key=COLUMNS.index)


def main(argv: list[str]) -> int:
    try:
        one_repo()
    except Refused as exc:
        print(exc, file=sys.stderr)
        return 1
    if len(argv) == 2 and argv[0] == "column" and argv[1].isdigit():
        try:
            mapped = mapping(tracker_file())
            repo = _graphql(COLUMN, owner="{owner}", name="{repo}", issue=int(argv[1]))[
                "repository"
            ]
        except Refused as exc:
            print(exc, file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as exc:
            print(exc.stderr.strip(), file=sys.stderr)
            return 1
        print(column_of(repo, mapped))
        return 0
    if len(argv) == 4 and argv[0] == "field" and argv[1].isdigit():
        try:
            set_field(int(argv[1]), argv[2], argv[3])
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(getattr(exc, "stderr", "").strip() or exc, file=sys.stderr)
            return 1
        return 0
    if len(argv) != 2 or not argv[0].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    try:
        move(int(argv[0]), mapping(tracker_file()).get(argv[1], argv[1]))
    except (ValueError, Refused, subprocess.CalledProcessError) as exc:
        print(getattr(exc, "stderr", "").strip() or exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
