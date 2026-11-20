"""The gatekeeper's GitHub adapter: the tracker, forge and evidence ports (gatekeeper.py, Ports) through `gh`, in the
checkout's repo. gatekeeper.py loads it beside itself by path (sibling) and hands it `Refused`, `public` and `denied`;
nothing else imports it.

Every call goes through gh(), which checks each posted body against the local deny list first (denied), and every read
GraphQL serves goes through fast(), which reads REST instead where GitHub refuses GraphQL with a 403, as a cloud
session's proxy does. Reads return GitHub's GraphQL node shapes (ISSUE, PULL), which the policy reads.
"""

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar


# gatekeeper.py sets these three once it has loaded this module (sibling): the refusal that exits 1, the masking of a
# home or temp path in a posted text, and the deny list's refusal of a text naming a listed term
class Refused(Exception):
    """A reason to stop with exit 1, printed as is: gatekeeper.py's own, once it loads this module."""


def public(text: str) -> str:
    """`text` as posted: gatekeeper.py's public(), once it loads this module."""
    return text


def denied(text: str) -> None:
    """Refuse to post `text` naming a deny-list term: gatekeeper.py's denied(), once it loads this module."""


# the collaborator permissions that can write; GitHub's `permission` field reads `maintain` as `write`
WRITE = {"admin", "maintain", "write"}


NOTE = "id author { login } body createdAt lastEditedAt isMinimized viewerCanMinimize"


SPECCED = f"number state body createdAt lastEditedAt labels(first: 50) {{ nodes {{ name }} }} comments(last: 100) {{ totalCount nodes {{ {NOTE} }} }}"


ASSIGNEES = "assignees(first: 10) { nodes { login } }"


# what land needs to edit a PR's comment, and check merge to name one it can't (gatekeeper.py's session_links)
EDITABLE = "databaseId url viewerCanUpdate"


# who added `approved:spec` (approver) and who was assigned when (release); ponytail: the newest 100 such events
EVENTS = """timelineItems(last: 100, itemTypes: [LABELED_EVENT, ASSIGNED_EVENT]) { nodes { __typename
  ... on LabeledEvent { createdAt actor { __typename login } label { name } }
  ... on AssignedEvent { createdAt assignee { ... on User { login } ... on Bot { login } } } } }"""


# an issue with its author and its native parent (an epic), which spec_policy() reads, its assignees and events
ISSUE = f"{SPECCED} author {{ login }} parent {{ {SPECCED} }} {ASSIGNEES} {EVENTS}"


# a PR's review threads, which PULL reads and rest_threads() asks for alone where GitHub's REST has none
THREADS = f"reviewThreads(first: 100) {{ totalCount nodes {{ isResolved comments(first: 50) {{ nodes {{ body {EDITABLE} }} }} }} }}"


PULL = f"""id number url title isCrossRepository author {{ __typename login }} {ASSIGNEES} state isDraft mergeable autoMergeRequest {{ enabledAt }} isInMergeQueue body viewerCanUpdate baseRefName baseRefOid headRefName headRefOid baseRepository {{ nameWithOwner defaultBranchRef {{ name }} }} labels(first: 50) {{ nodes {{ name }} }} comments(last: 100) {{ totalCount nodes {{ {NOTE} {EDITABLE} }} }}
  files(first: 100) {{ totalCount nodes {{ path changeType additions deletions }} }} latestReviews(first: 100) {{ nodes {{ state author {{ login }} }} }}
  reviews(last: 100) {{ totalCount nodes {{ author {{ login }} state body commit {{ oid }} {EDITABLE} }} }}
  {THREADS}
  authored: commits(first: 100) {{ totalCount nodes {{ commit {{ authors(first: 5) {{ totalCount nodes {{ user {{ login }} }} }} committer {{ user {{ login }} }} }} }} }}
  timelineItems(last: 100, itemTypes: [LABELED_EVENT, READY_FOR_REVIEW_EVENT]) {{ nodes {{ __typename
    ... on LabeledEvent {{ createdAt label {{ name }} }} ... on ReadyForReviewEvent {{ createdAt }} }} }}
  mergeQueueEntry {{ state position headCommit {{ committedDate checkSuites {{ totalCount }} }} }}
  removals: timelineItems(last: 50, itemTypes: [REMOVED_FROM_MERGE_QUEUE_EVENT]) {{ nodes {{
    ... on RemovedFromMergeQueueEvent {{ reason createdAt beforeCommit {{ oid }} }} }} }}
  commits(last: 1) {{ nodes {{ commit {{ statusCheckRollup {{ contexts(first: 100) {{ totalCount nodes {{
    __typename ... on CheckRun {{ name status conclusion startedAt completedAt checkSuite {{ status workflowRun {{ workflow {{ name }} }} }} }}
    ... on StatusContext {{ context state createdAt targetUrl }} }} }} }} }} }} }}
  closingIssuesReferences(first: 50) {{ nodes {{ repository {{ nameWithOwner }} {ISSUE} }} }}"""


def merged_labelled(branch: str, name: str) -> list[int]:
    """The merged PRs into `branch` that carry the label `name`."""
    # ponytail: one page of 100 through GraphQL; page when a feature branch takes more such PRs than that
    found = fast(
        lambda: gh(
            "pr",
            "list",
            "--base",
            branch,
            "--state",
            "merged",
            "--label",
            name,
            "--limit",
            "100",
            "--json",
            "number",
            "--jq",
            ".[].number",
        ),
        # REST: every closed PR into the branch, the merged ones carrying the label
        lambda: "\n".join(
            str(pull["number"])
            for pull in rest_pages(f"pulls?state=closed&base={branch}&per_page=100")
            if pull.get("merged_at")
            and name in {label["name"] for label in pull.get("labels") or []}
        ),
    )
    return [int(number) for number in found.split()]


def open_pulls(limit: int) -> list[dict[str, Any]]:
    """The repo's open PRs, up to `limit`, each with its number, branch, base, whether it is a draft, body and closing references (each naming its
    issue's repo as `nameWithOwner`, as the PR query does), in one call."""
    found = fast(
        lambda: json.loads(
            gh(
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                str(limit),
                "--json",
                "number,headRefName,baseRefName,isDraft,body,closingIssuesReferences",
            )
        ),
        # REST has no closing references: closed() reads each body's lines, as it does for the PR checked
        lambda: [
            {
                "number": other["number"],
                "headRefName": other["head"]["ref"],
                "baseRefName": other["base"]["ref"],
                "isDraft": bool(other.get("draft")),
                "body": other.get("body") or "",
                "closingIssuesReferences": [],
            }
            for other in rest_pages("pulls?state=open&per_page=100")[:limit]
        ],
    )
    for other in found:
        nodes = other["closingIssuesReferences"]
        for issue in nodes:
            where = issue["repository"]
            issue["repository"] = {"nameWithOwner": f"{where['owner']['login']}/{where['name']}"}
        other["closingIssuesReferences"] = {"nodes": nodes}
    return found


def open_pull_files(limit: int) -> list[dict[str, Any]]:
    """Up to `limit` open PRs, each with its number, base, head commit and the paths it changes (`files`), in one call.
    `gh pr list` names a PR's first 100 files only, so a PR with 100 has all of its files re-read through REST's pages
    (GitHub's own cap there is 3000), and an overlap past the 100th file is never missed."""

    def every_file(number: int) -> list[str]:
        # objects, not `.[].filename`: `gh --jq` prints a string raw, which rest_pages can't read as JSON
        return [file["filename"] for file in rest_pages(f"pulls/{number}/files?per_page=100")]

    return fast(  # type: ignore[no-any-return]
        lambda: [
            {
                **pull,
                "files": every_file(pull["number"])
                if len(pull["files"]) >= 100
                else [file["path"] for file in pull["files"]],
            }
            for pull in json.loads(
                gh(
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--limit",
                    str(limit),
                    "--json",
                    "number,baseRefName,headRefOid,files",
                )
            )
        ],
        lambda: [
            {
                "number": other["number"],
                "baseRefName": other["base"]["ref"],
                "headRefOid": other["head"]["sha"],
                "files": every_file(other["number"]),
            }
            for other in rest_pages("pulls?state=open&per_page=100")[:limit]
        ],
    )


def texts(data: str) -> list[str]:
    """The text GitHub will publish from a post's `data`: every string a JSON payload holds, decoded (a review's body
    and its inline comments), else the data itself (a comment's body)."""
    try:
        found: list[Any] = [json.loads(data)]
    except ValueError:
        return [data]
    strings = []
    while found:
        value = found.pop()
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict | list):
            found.extend(value.values() if isinstance(value, dict) else value)
    return strings


def gh(*args: str, data: str | None = None) -> str:
    if data is not None:  # every comment and review approvals.py posts goes as `data`
        for text in texts(data):
            denied(text)
    backoff = 60
    while True:
        try:
            return subprocess.run(
                ["gh", *args], input=data, check=True, capture_output=True, text=True
            ).stdout
        except subprocess.CalledProcessError as exc:
            if (
                pause := rate_limited(str(exc.stderr), backoff, args[:2] == ("api", "graphql"))
            ) is None:
                raise
            # jitter, so lands that waited on one reset do not all resume in the same second
            pause += random.randint(0, JITTER)
            until = time.time() + pause
            if wait_until is None or time.monotonic() + pause > wait_until:
                exc.stderr = f"{exc.stderr}\nGitHub rate limit, resets at {time.strftime('%H:%M UTC', time.gmtime(until))}"
                raise
            said = (
                f"GitHub rate limit, waiting until {time.strftime('%H:%M UTC', time.gmtime(until))}"
            )
            # in slices that each print, so wait-for's stall check (a log silent for 300 s) never kills the wait
            for left in range(pause, 0, -SLICE):
                print(said, file=sys.stderr, flush=True)
                time.sleep(min(left, SLICE))
            backoff = min(backoff * 2, 600)


# land --wait sets this (time.monotonic) to the end of its ceiling: a rate limit then waits, else gh() fails with the reset time
wait_until: float | None = None
JITTER = 60  # most seconds of random delay added to a rate-limit wait
SLICE = 60  # seconds between the lines a rate-limit wait prints


def rate_limited(stderr: str, backoff: int, graphql: bool = False) -> int | None:
    """Seconds to wait when `stderr` is a GitHub rate-limit refusal, else None. A secondary limit waits for the
    `Retry-After` the error shows, else `backoff` (60 s, doubling). A primary one (`API rate limit exceeded`, or
    GitHub's `already exceeded for user ID n`) reads its bucket from `gh api rate_limit`, which costs no quota: an
    empty bucket waits to its reset, one with calls left was refused for the per-minute limit and waits `backoff`.
    The bucket is GraphQL's for `gh api graphql` and for any gh command whose error says `GraphQL:`, else REST's.
    ponytail: gh's error text shows no headers, so Retry-After is read only where it appears in the message; and a
    refusal may carry no HTTP status (a GraphQL one is HTTP 200), so the message alone is read."""
    graphql = graphql or "GraphQL:" in stderr
    if (
        re.search(r"secondary rate limit|abuse detection", stderr, re.IGNORECASE)
        or "HTTP 429" in stderr
    ):
        found = re.search(r"retry[- ]after:? *(\d+)", stderr, re.IGNORECASE)
        return int(found[1]) if found else backoff
    if not re.search(r"API rate limit (already )?exceeded", stderr):
        return None
    try:
        remaining, reset = map(
            int,
            subprocess.run(
                [
                    "gh",
                    "api",
                    "rate_limit",
                    "--jq",
                    f'.resources.{"graphql" if graphql else "core"} | "\\(.remaining) \\(.reset)"',
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.split(),
        )
    except (subprocess.CalledProcessError, ValueError):
        return backoff
    return backoff if remaining else max(reset - int(time.time()), 0) + 1


def _graphql(query: str, **fields: object) -> Any:
    args = [arg for key, value in fields.items() for arg in ("-F", f"{key}={value}")]
    # gh fills {owner} and {repo} from the current checkout
    out = gh(
        "api", "graphql", "-f", f"query={query}", "-F", "owner={owner}", "-F", "name={repo}", *args
    )
    return json.loads(out)["data"]["repository"]


def _repository(fields: str) -> str:
    return f"query($owner: String!, $name: String!, $n: Int!) {{ repository(owner: $owner, name: $name) {{ {fields} }} }}"


# how GitHub, or a cloud session's proxy in front of it, refuses GraphQL: `gh` ends its error with a 403, or, for a job
# token a private organization repository withholds fields from, prints GraphQL's FORBIDDEN message
REFUSALS = ("HTTP 403", "Resource not accessible by integration")


def refused(stderr: str | None) -> bool:
    """Whether `gh`'s stderr says GitHub refused this token or path, as opposed to failing for another reason."""
    return any(text in (stderr or "") for text in REFUSALS)


# set once GraphQL was refused, so the rest of this run reads REST without asking GraphQL again; GATEKEEPER_REST_ONLY=1
# sets it from the start, so a check can force the REST path on a token GraphQL would answer
_rest_only = os.environ.get("GATEKEEPER_REST_ONLY") == "1"


Answer = TypeVar("Answer")


def fast(graphql: Callable[[], Answer], rest: Callable[[], Answer]) -> Answer:
    """GraphQL's answer, the fast path, or REST's where GitHub refuses GraphQL with a 403, as a cloud session's proxy
    does. REST reads the same fields call by call, in the same shape. After one refusal the run reads REST alone, so a
    run there makes one refused GraphQL call at most. Any other error raises."""
    global _rest_only
    if not _rest_only:
        try:
            return graphql()
        except subprocess.CalledProcessError as exc:
            if not refused(exc.stderr):
                raise
            _rest_only = True
    return rest()


def rest(path: str) -> Any:
    return json.loads(gh("api", path))


def rest_pages(path: str, items: str = ".[]") -> list[Any]:
    """Every item of a paged REST list, `items` picking them out of each page."""
    out = gh("api", "--paginate", f"repos/{{owner}}/{{repo}}/{path}", "--jq", items)
    return [json.loads(line) for line in out.splitlines()]


def actor(user: dict[str, Any] | None) -> dict[str, Any] | None:
    """A REST user as GraphQL names it: its login without the `[bot]` REST adds, and its type."""
    if not user:
        return None
    return {"login": user["login"].removesuffix("[bot]"), "__typename": user.get("type") or "User"}


def rest_notes(number: int) -> dict[str, Any]:
    """An issue's or PR's comments from REST, every page, as GraphQL's `comments` reads them. REST has no edit time,
    so a note has no `lastEditedAt` (versions() then reads its text alone), only `updatedAt`, which every edit moves;
    nor can this account's right to minimize be read, so approve() minimizes nothing it read here."""
    nodes = [
        {
            "id": found["node_id"],
            # what gatekeeper.py's session_links() names a comment by and edits it at; REST gives no right to edit it
            "databaseId": found.get("id"),
            "url": found.get("html_url"),
            "author": actor(found.get("user")),
            "body": found.get("body") or "",
            "createdAt": found["created_at"],
            "updatedAt": found["updated_at"],
            "isMinimized": bool(found.get("minimized")),
            "viewerCanMinimize": False,
        }
        for found in rest_pages(f"issues/{number}/comments?per_page=100")
    ]
    return {"totalCount": len(nodes), "nodes": nodes}


# REST timeline events as GraphQL's timelineItems types them
TIMELINE = {
    "labeled": "LabeledEvent",
    "assigned": "AssignedEvent",
    "ready_for_review": "ReadyForReviewEvent",
}


def rest_timeline(number: int, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """An issue's or PR's label, assign and ready events from REST's timeline, every page (`events`, once read)."""
    nodes = []
    if events is None:
        events = rest_pages(f"issues/{number}/timeline?per_page=100")
    for event in events:
        if (kind := TIMELINE.get(event.get("event"))) is None:
            continue
        found: dict[str, Any] = {"__typename": kind, "createdAt": event.get("created_at")}
        if kind == "LabeledEvent":
            found |= {"actor": actor(event.get("actor")), "label": event.get("label")}
        if kind == "AssignedEvent":
            found["assignee"] = actor(event.get("assignee"))
        nodes.append(found)
    return {"nodes": nodes}


def rest_specced(found: dict[str, Any]) -> dict[str, Any]:
    """The SPECCED fields of a REST issue: its body and labels, and its comments read too. No `lastEditedAt`: REST has
    no edit time, so the spec's text names its version (versions)."""
    return {
        "number": found["number"],
        "state": found["state"].upper(),
        "body": found.get("body") or "",
        "createdAt": found["created_at"],
        "updatedAt": found["updated_at"],
        "labels": {"nodes": [{"name": label["name"]} for label in found.get("labels") or []]},
        "comments": rest_notes(found["number"]),
    }


def rest_issue(number: int) -> dict[str, Any] | None:
    """Issue #number as ISSUE reads it, from REST; None for a pull request, as GraphQL's `... on Issue` gives."""
    found = rest(f"repos/{{owner}}/{{repo}}/issues/{number}")
    if "pull_request" in found:
        return None
    try:
        parent = rest_specced(rest(f"repos/{{owner}}/{{repo}}/issues/{number}/parent"))
    except subprocess.CalledProcessError as exc:
        if "HTTP 404" not in (exc.stderr or ""):
            raise
        parent = None
    return rest_specced(found) | {
        "author": actor(found.get("user")),
        "parent": parent,
        "assignees": {"nodes": [actor(user) for user in found.get("assignees") or []]},
        "timelineItems": rest_timeline(number),
    }


# REST's file status as GraphQL's changeType
CHANGE_TYPES = {"added": "ADDED", "removed": "DELETED", "renamed": "RENAMED", "copied": "COPIED"}


# a trailer naming a commit's co-author, which GraphQL resolves to an account and REST does not
CO_AUTHOR = re.compile(r"^co-authored-by:", re.IGNORECASE | re.MULTILINE)


def rest_authored(number: int, total: int) -> dict[str, Any]:
    """A PR's commits as `authored` reads them, from REST: each commit's author and committer account. A co-author
    trailer, which only GraphQL resolves to an account, counts as an author not read, so exempt() exempts nothing."""
    nodes = []
    for found in rest_pages(f"pulls/{number}/commits?per_page=100"):
        authors = [{"user": actor(found.get("author"))}]
        committer = actor(found.get("committer"))
        # GitHub's web-flow commits for a bot or the API: GraphQL gives that committer no account
        if committer and committer["login"] == "web-flow":
            committer = None
        co = len(CO_AUTHOR.findall((found.get("commit") or {}).get("message") or ""))
        nodes.append(
            {
                "commit": {
                    "authors": {"totalCount": 1 + co, "nodes": authors},
                    "committer": {"user": committer},
                }
            }
        )
    return {"totalCount": total, "nodes": nodes}


def rest_latest(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each reviewer's newest review that approves, requests changes or was dismissed: a comment-only review
    leaves a reviewer's request for changes standing, as GitHub's review decision reads it."""
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if review["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[(review.get("author") or {}).get("login") or ""] = review
    return list(latest.values())


def rest_checks(head: str) -> dict[str, Any]:
    """The head's checks as `statusCheckRollup` reads them, from REST: every check run (each rerun too), named by its
    workflow, and each status context's newest state."""
    runs = rest_pages(f"commits/{head}/check-runs?filter=all&per_page=100", ".check_runs[]")
    suites = {
        suite["id"]: suite
        for suite in rest_pages(f"commits/{head}/check-suites?per_page=100", ".check_suites[]")
    }
    flows = {
        run["check_suite_id"]: run["name"]
        for run in rest_pages(f"actions/runs?head_sha={head}&per_page=100", ".workflow_runs[]")
    }
    nodes: list[dict[str, Any]] = []
    for run in runs:
        suite = (run.get("check_suite") or {}).get("id")
        flow = flows.get(suite)
        nodes.append(
            {
                "__typename": "CheckRun",
                "name": run["name"],
                "status": (run.get("status") or "").upper(),
                "conclusion": (run.get("conclusion") or "").upper() or None,
                "startedAt": run.get("started_at"),
                "completedAt": run.get("completed_at"),
                "checkSuite": {
                    "status": ((suites.get(suite) or {}).get("status") or "").upper(),
                    "workflowRun": {"workflow": {"name": flow}} if flow else None,
                },
            }
        )
    combined = rest(f"repos/{{owner}}/{{repo}}/commits/{head}/status?per_page=100")
    for status in combined.get("statuses") or []:
        nodes.append(
            {
                "__typename": "StatusContext",
                "context": status["context"],
                "state": status["state"].upper(),
                "createdAt": status.get("created_at"),
                "targetUrl": status.get("target_url"),
            }
        )
    total = len(nodes) - len(combined.get("statuses") or []) + combined.get("total_count", 0)
    return {"contexts": {"totalCount": total, "nodes": nodes}}


def rest_threads(number: int) -> dict[str, Any]:
    """A PR's review threads, whether each is resolved, from the review-thread route a cloud session's GitHub proxy
    serves. GitHub's own REST has none and answers 404: there, as for a job token in a private organization repository,
    whose GraphQL withholds other fields of PULL but not these, the threads come from GraphQL alone. Where that fails
    too, the error raises: unresolved threads are never read as none. Each thread's comments, which the proxy's route
    names by id alone, come from the PR's review comments, with no right to edit them (session_links())."""
    try:
        threads = rest(f"repos/{{owner}}/{{repo}}/pulls/{number}/ccr/review_threads")
    except subprocess.CalledProcessError as exc:
        if "HTTP 404" not in (exc.stderr or ""):
            raise
        found: dict[str, Any] = _graphql(
            _repository(f"pullRequest(number: $n) {{ {THREADS} }}"), n=number
        )
        return found["pullRequest"]["reviewThreads"]
    listed = {found["id"]: found for found in rest_pages(f"pulls/{number}/comments?per_page=100")}
    nodes = [
        {
            "isResolved": bool(thread.get("resolved")),
            "comments": {
                "nodes": [
                    {
                        "body": found.get("body") or "",
                        "databaseId": found["id"],
                        "url": found.get("html_url"),
                    }
                    for found in (listed.get(each) for each in thread.get("comment_ids") or [])
                    if found is not None
                ]
            },
        }
        for thread in threads
    ]
    return {"totalCount": len(nodes), "nodes": nodes}


def rest_pull(pr: int) -> dict[str, Any]:
    """PR #pr as PULL reads it, from REST, call by call. `closingIssuesReferences` is empty, since REST has no such
    link: the PR's issues are its body's `Closes`, `Part of` and `Implements` lines (closing_issues). Whether it is in
    a merge queue can't be read: `isInMergeQueue` is None, which unsignable() refuses unless a cloud session's loop.md
    says `merge_queue: false`."""
    found = rest(f"repos/{{owner}}/{{repo}}/pulls/{pr}")
    base, head = found["base"], found["head"]
    events = rest_pages(f"issues/{pr}/timeline?per_page=100")
    reviews = [
        {
            "author": actor(review.get("user")),
            "state": review["state"],
            "body": review.get("body") or "",
            "commit": {"oid": review.get("commit_id") or ""},
            "databaseId": review.get("id"),
            "url": review.get("html_url"),
        }
        for review in rest_pages(f"pulls/{pr}/reviews?per_page=100")
    ]
    files = [
        {
            "path": file["filename"],
            "changeType": CHANGE_TYPES.get(file["status"], "MODIFIED"),
            "additions": file.get("additions"),
            "deletions": file.get("deletions"),
        }
        for file in pr_changes(pr)
    ]
    state = "MERGED" if found.get("merged") else found["state"].upper()
    return {
        "id": found["node_id"],
        "number": found["number"],
        "url": found.get("html_url", ""),
        "title": found["title"],
        "isCrossRepository": (head.get("repo") or {}).get("full_name") != base["repo"]["full_name"],
        "author": actor(found.get("user")),
        "assignees": {"nodes": [actor(user) for user in found.get("assignees") or []]},
        "state": state,
        "isDraft": bool(found.get("draft")),
        # REST's true or false, or null while GitHub computes it, as GraphQL's MergeableState reads them
        "mergeable": {True: "MERGEABLE", False: "CONFLICTING"}.get(
            found.get("mergeable"), "UNKNOWN"
        ),
        "autoMergeRequest": {"enabledAt": None} if found.get("auto_merge") else None,
        "isInMergeQueue": None,
        "body": found.get("body") or "",
        "baseRefName": base["ref"],
        # the base branch's tip now, as GraphQL's baseRefOid is; REST's base.sha is the tip when the PR last synced
        "baseRefOid": rest(f"repos/{{owner}}/{{repo}}/branches/{base['ref']}")["commit"]["sha"],
        "headRefName": head["ref"],
        "headRefOid": head["sha"],
        "baseRepository": {
            "nameWithOwner": base["repo"]["full_name"],
            "defaultBranchRef": {"name": base["repo"]["default_branch"]},
        },
        "labels": {"nodes": [{"name": label["name"]} for label in found.get("labels") or []]},
        "comments": rest_notes(pr),
        "files": {"totalCount": found.get("changed_files") or len(files), "nodes": files},
        "latestReviews": {"nodes": rest_latest(reviews)},
        "reviews": {"totalCount": len(reviews), "nodes": reviews},
        "reviewThreads": rest_threads(pr),
        "authored": rest_authored(pr, found.get("commits") or 0),
        "timelineItems": rest_timeline(pr, events),
        "commits": {"nodes": [{"commit": {"statusCheckRollup": rest_checks(head["sha"])}}]},
        "closingIssuesReferences": {"nodes": []},
        **rest_queue(found, events),
    }


# the REST timeline's merge-queue events
QUEUE_ADDED, QUEUE_REMOVED = "added_to_merge_queue", "removed_from_merge_queue"
# the check run conclusions that make a merge-queue group red: a run cancelled there (its group rebuilt, or the entry
# dequeued) failed nothing
GROUP_RED = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE"}


def rest_queue(found: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """The PR's `mergeQueueEntry` and `removals` as PULL reads them, from REST, which has neither: `found`, its REST
    pull, and `events`, its timeline. The entry, only while the timeline's newest queue event is an add (GitHub may
    delete a group's ref a while after it took the PR out): awaiting checks on its group's commit while GitHub's
    readonly ref for it (`gh-readonly-queue/<base>/pr-<n>-<sha>`) exists, else queued; none, and no removal, for a PR
    whose timeline has no queue event.
    A `removed_from_merge_queue` event names no reason, so each gets GraphQL's from what REST reads on its group (the
    commit of the newest `merge_group` run on such a ref since the PR's add before it): `merged`, the last one, when
    GitHub reports the PR merged or the group's commit is in the base (GitHub takes it out a moment before it reports
    the merge); `failed_checks` when a check the base requires failed on the group's commit; `merge_conflict`, the last
    one, when GitHub reports the PR conflicting or is still working that out; else `unknown`, which counts for nothing, as `checks_timed_out` and
    `manual` do."""
    number, base, merged = found["number"], found["base"]["ref"], bool(found.get("merged"))
    prefix = f"gh-readonly-queue/{base}/pr-{number}-"
    queue = [event for event in events if event.get("event") in (QUEUE_ADDED, QUEUE_REMOVED)]
    entry = None
    if not queue:  # never in a merge queue: no ref, no group
        return {"mergeQueueEntry": entry, "removals": {"nodes": []}}
    if not merged and queue[-1]["event"] == QUEUE_ADDED:
        entry = {"state": "QUEUED", "position": None, "headCommit": None}
        if refs := rest_pages(f"git/matching-refs/heads/{prefix}"):
            group = refs[-1]["object"]["sha"]
            made = rest(f"repos/{{owner}}/{{repo}}/commits/{group}")["commit"]["committer"]["date"]
            suites = rest(f"repos/{{owner}}/{{repo}}/commits/{group}/check-suites?per_page=1")
            commit = {
                "committedDate": made,
                "checkSuites": {"totalCount": suites.get("total_count") or 0},
            }
            entry = {"state": "AWAITING_CHECKS", "position": None, "headCommit": commit}
    removed = [event for event in queue if event["event"] == QUEUE_REMOVED]
    if not removed:
        return {"mergeQueueEntry": entry, "removals": {"nodes": []}}
    # ponytail: the repo's newest 100 `merge_group` runs; a removal whose group fell out of them counts for nothing
    runs = rest("repos/{owner}/{repo}/actions/runs?event=merge_group&per_page=100")
    groups = sorted(
        (run.get("created_at") or "", run["head_sha"])
        for run in runs.get("workflow_runs") or []
        if (run.get("head_branch") or "").startswith(prefix)
    )
    required = required_checks(base) if groups else set()
    adds = [event.get("created_at") or "" for event in queue if event["event"] == QUEUE_ADDED]
    nodes = []
    for event in removed:
        at, last = event.get("created_at") or "", event is removed[-1]
        since = max((added for added in adds if added <= at), default="")
        group = next((sha for made, sha in reversed(groups) if since <= made <= at), None)
        reason, commit = "unknown", group
        if last and merged:
            reason, commit = "merged", found.get("merge_commit_sha") or group
        elif group and group_red(group, required):
            reason = "failed_checks"
        elif last and group and in_base(base, group):
            reason = "merged"
        # false: conflicting; null: GitHub working it out again, which the gatekeeper waits on, as on a host
        elif last and found.get("mergeable") is not True:
            reason = "merge_conflict"
        nodes.append(
            {"reason": reason, "createdAt": at, "beforeCommit": {"oid": commit} if commit else None}
        )
    return {"mergeQueueEntry": entry, "removals": {"nodes": nodes}}


def group_red(group: str, required: set[str]) -> bool:
    """Whether a check the base requires (any, where it requires none) failed on the merge queue's commit `group`."""
    return any(
        run["conclusion"] in GROUP_RED
        for name, run in commit_checks(group).items()
        if not required or name in required
    )


def in_base(base: str, commit: str) -> bool:
    """Whether `commit` is in `base` already, False where GitHub can't compare them."""
    try:
        return merge_base(base, commit) == commit
    except subprocess.CalledProcessError:
        return False


def pull_status(pr: int) -> dict[str, Any]:
    """What a caller that only reads a PR's status needs (`state`, `baseRefName`, `headRefOid`, `mergeable`), from one
    REST call in PULL's shape. GraphQL's PULL is dozens of fields and counts toward the shared GraphQL limit; REST's
    `pulls/N` has these four. Anything else (comments, reviews, labels, checks) stays on pull_request()."""
    found = rest(f"repos/{{owner}}/{{repo}}/pulls/{pr}")
    return {
        "number": found["number"],
        "state": "MERGED" if found.get("merged") else found["state"].upper(),
        "baseRefName": found["base"]["ref"],
        "headRefOid": found["head"]["sha"],
        "mergeable": {True: "MERGEABLE", False: "CONFLICTING"}.get(
            found.get("mergeable"), "UNKNOWN"
        ),
    }


def pull_request(pr: int) -> dict[str, Any]:
    return fast(
        lambda: _graphql(_repository(f"pullRequest(number: $n) {{ {PULL} }}"), n=pr)["pullRequest"],
        lambda: rest_pull(pr),
    )


def pr_changes(number: int) -> list[dict[str, Any]]:
    """Every file a PR changes, with its patch, as GitHub's REST API pages them: up to 3000."""
    out = gh(
        "api",
        "--paginate",
        f"repos/{{owner}}/{{repo}}/pulls/{number}/files?per_page=100",
        "--jq",
        ".[]",
    )
    return [json.loads(line) for line in out.splitlines()]


def merged_pull(number: int) -> dict[str, Any] | None:
    """PR #number as GitHub's REST API returns it, when it was merged; None for an open or closed PR, or an issue."""
    try:
        found: dict[str, Any] = json.loads(gh("api", f"repos/{{owner}}/{{repo}}/pulls/{number}"))
    except subprocess.CalledProcessError as exc:
        if "Not Found" in exc.stderr:
            return None
        raise
    return found if found.get("merged") else None


def merge_base(base: str, head: str) -> str:
    """The commit GitHub diffs a PR's head against: where it branched from its base."""
    return gh(
        "api", f"repos/{{owner}}/{{repo}}/compare/{base}...{head}", "--jq", ".merge_base_commit.sha"
    ).strip()


# GitHub's answer to a rules read on a private repo of a free plan
PLAN_LIMIT = "Upgrade to GitHub Pro"


class Required(set):
    """The checks a base requires (required_checks), and `queue`: the merge method (`MERGE`, `SQUASH` or `REBASE`) of
    the GitHub merge queue its rules require, None without one, which picks land's local merge queue."""

    queue: str | None = None


def required_checks(base: str) -> Required:
    """The checks the base branch requires, from its live rules: its rulesets' and its branch protection's, with the
    merge method of a `merge_queue` rule as `queue`, which picks land's GitHub merge queue. A private repo on GitHub's
    free plan has no rulesets: that 403 reads as none, and any other error raises."""
    try:
        rulesets = gh(
            "api",
            "--paginate",
            f"repos/{{owner}}/{{repo}}/rules/branches/{base}",
            "--jq",
            '.[] | if .type == "merge_queue" then ":merge_queue:" + (.parameters.merge_method // "MERGE")'
            ' elif .type == "required_status_checks" then .parameters.required_status_checks[].context else empty end',
        )
    except subprocess.CalledProcessError as error:
        if "(HTTP 403)" not in (error.stderr or "") or PLAN_LIMIT not in error.stderr:
            raise
        print(
            f"GitHub enforces no rules on {base} here (its plan has none): land's proofs are the only gate"
        )
        rulesets = ""
    protection = gh(
        "api",
        f"repos/{{owner}}/{{repo}}/branches/{base}",
        "--jq",
        ".protection.required_status_checks.contexts // [] | .[]",
    )
    queue = [word for word in rulesets.split() if word.startswith(":merge_queue")]
    found = Required(set((rulesets + protection).split()) - set(queue))
    if queue:
        found.queue = queue[0].rpartition(":")[2]
    return found


def tree(sha: str) -> dict[str, tuple[str, str]] | None:
    """The (mode, blob SHA) of every path in commit `sha`'s tree, from GitHub's trees API; None when GitHub truncates it.
    ponytail: one recursive read, up to GitHub's 100,000 entries; read each touched directory when a repo outgrows it."""
    found = json.loads(gh("api", f"repos/{{owner}}/{{repo}}/git/trees/{sha}?recursive=1"))
    if found["truncated"]:
        return None
    return {
        entry["path"]: (entry["mode"], entry["sha"])
        for entry in found["tree"]
        if entry["type"] != "tree"
    }


def head_pushed(pull: dict[str, Any]) -> str | None:
    """When the head commit was last pushed to the PR's branch, from GitHub's repository activity (pushes, force
    pushes, the branch's creation); None when it lists none. ponytail: the newest 100 activities of a same-repo branch;
    page further, or read a fork's, when a PR here needs it."""
    out = gh(
        "api",
        f"repos/{{owner}}/{{repo}}/activity?ref=refs/heads/{pull['headRefName']}&per_page=100",
        "--jq",
        f'[.[] | select(.after == "{pull["headRefOid"]}") | .timestamp] | first // ""',
    ).strip()
    return out or None


def issue_node(number: int) -> dict[str, Any]:
    def rest_read() -> dict[str, Any]:
        found = rest_issue(number)
        if found is None:
            raise Refused(f"#{number} is a pull request, not an issue")
        return found

    node: dict[str, Any] = fast(
        lambda: _graphql(_repository(f"issue(number: $n) {{ {ISSUE} }}"), n=number)["issue"],
        rest_read,
    )
    return node


def label(number: int, name: str, add: bool) -> None:
    """Add (GitHub creates a missing label) or remove a label on an issue or PR; removing an absent one is fine."""
    path = f"repos/{{owner}}/{{repo}}/issues/{number}/labels"
    if add:
        gh("api", path, "-f", f"labels[]={name}", "--silent")
        return
    try:
        gh("api", "-X", "DELETE", f"{path}/{name}", "--silent")
    except subprocess.CalledProcessError as exc:
        if "Label does not exist" not in exc.stderr:
            raise


def assign(number: int, login: str, add: bool) -> None:
    """Add or remove an assignee of an issue or PR; GitHub ignores an absent one."""
    gh(
        "api",
        *(() if add else ("-X", "DELETE")),
        f"repos/{{owner}}/{{repo}}/issues/{number}/assignees",
        "-f",
        f"assignees[]={login}",
        "--silent",
    )


def close_issue(number: int) -> None:
    """Close an issue as completed; closing a closed one is fine."""
    gh(
        "api",
        "-X",
        "PATCH",
        f"repos/{{owner}}/{{repo}}/issues/{number}",
        "-f",
        "state=closed",
        "--silent",
    )


def comment(number: int, body: str) -> str:
    """Post `body` on PR or issue `number`; the new comment's URL."""
    return gh(
        "api",
        f"repos/{{owner}}/{{repo}}/issues/{number}/comments",
        "-F",
        "body=@-",
        "--jq",
        ".html_url",
        data=public(body),
    ).strip()


def minimize(comment_id: str) -> None:
    """Collapse a comment on GitHub as outdated; it stays readable, and the gate still reads it."""
    gh(
        "api",
        "graphql",
        "-f",
        "query=mutation($id: ID!) { minimizeComment(input: {subjectId: $id, classifier: OUTDATED}) { clientMutationId } }",
        "-f",
        f"id={comment_id}",
        "--silent",
    )


viewer_login: dict[str, str] = {}  # the login `gh` runs as, read once per process (viewer)


def viewer() -> str | None:
    """The login of the account `gh` runs as; None for a token `GET /user` refuses, such as a workflow's installation
    token (`github.token`), where the PR's author and the repo's writers are the ones trusted (passes). Read once per
    process; a failure is not kept, so the next call asks again."""
    if login := viewer_login.get("login"):
        return login
    try:
        login = viewer_login["login"] = gh("api", "user", "--jq", ".login").strip()
    except subprocess.CalledProcessError:
        return None  # not cached: a network or rate-limit failure must not read as a token GitHub refuses
    return login


def writer(login: str) -> bool:
    """Whether `login` can write to the repo, by GitHub's collaborator permission; an account GitHub refuses to look
    up can't. ponytail: a bot's GraphQL login lacks the `bot` REST needs, so a bot author fails closed; add the
    suffix when a project's bot opens sub-issues."""
    try:
        permission = gh(
            "api",
            f"repos/{{owner}}/{{repo}}/collaborators/{login}/permission",
            "--jq",
            ".permission",
        )
    except subprocess.CalledProcessError as exc:
        # a cloud session's proxy refuses this path; the repo's own permissions answer it for the account running this
        # alone, and anyone else still can't, so a stranger never counts as a writer
        if not refused(exc.stderr) or login != viewer():
            return False
        try:
            mine = rest("repos/{owner}/{repo}").get("permissions") or {}
        except subprocess.CalledProcessError:
            return False
        return bool(mine.get("push") or mine.get("maintain") or mine.get("admin"))
    return permission.strip() in WRITE


def current_pr() -> int | None:
    def graphql() -> int | None:
        try:
            return int(gh("pr", "view", "--json", "number", "--jq", ".number"))
        except subprocess.CalledProcessError as exc:
            if "no pull requests found" in exc.stderr:
                return None
            raise

    def rest_read() -> int | None:
        # the open PR whose head is this branch of origin's repo, as `gh pr view` finds it
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        owner = rest("repos/{owner}/{repo}")["owner"]["login"]
        found = rest_pages(f"pulls?state=open&head={owner}:{branch}&per_page=100")
        return int(found[0]["number"]) if found else None

    return fast(graphql, rest_read)


# a remote URL's host and `owner/repo`: `scheme://[user@]host[:port]/owner/repo` or scp-like `[user@]host:owner/repo`,
# its path maybe led by extra slashes as gh allows, matched once trailing slashes and `.git` are cut (post_demo.sh
# parses it the same way)
REMOTE_URL = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://)?(?:[^@/]*@)?([^/:]+)(?::\d+)?[:/]/*([^/]+/[^/]+)", re.IGNORECASE
)


def github_repo(url: str) -> str | None:
    """The `owner/repo` a GitHub remote URL names, lowercased; None for another host."""
    found = REMOTE_URL.fullmatch(re.sub(r"(?:\.git)?/*$", "", url.rstrip("/")))
    return found[2].lower() if found and found[1].lower() == "github.com" else None


def one_repo() -> None:
    """Refuse a checkout whose remotes name several GitHub repos while none is gh's default (`gh repo set-default`,
    kept as `remote.<name>.gh-resolved`): gh then reads `{owner}/{repo}` and every `gh pr` as `upstream`, and a
    review or label lands on a repo nobody chose. Outside a checkout it passes, and gh says why it can't run."""
    remotes = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, check=False)
    repos = sorted(
        {
            repo
            for line in remotes.stdout.splitlines()
            if len(fields := line.split()) > 1 and (repo := github_repo(fields[1]))
        }
    )
    chosen = subprocess.run(
        ["git", "config", "--get-regexp", r"^remote\..*\.gh-resolved$"],
        capture_output=True,
        check=False,
    )
    if len(repos) > 1 and chosen.returncode:
        raise Refused(
            f"this checkout's remotes name {', '.join(repos)} and gh has no default among them, so gh would pick one"
            " itself: run `gh repo set-default <owner>/<repo>` once, naming the repo the PRs live in"
        )


def diff_lines(base: str, head: str) -> dict[str, list[int]]:
    """The lines a review at `head` can comment on, per file: the new side of GitHub's diff of base...head (added and
    context lines). ponytail: one compare, up to the 300 files it lists."""
    out = gh(
        "api",
        f"repos/{{owner}}/{{repo}}/compare/{base}...{head}",
        "--jq",
        ".files[] | {filename, patch}",
    )
    found: dict[str, list[int]] = {}
    for entry in (json.loads(line) for line in out.splitlines()):
        lines, number = found.setdefault(entry["filename"], []), 0
        for line in (entry.get("patch") or "").split("\n"):
            hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            if hunk:
                number = int(hunk.group(1))
            elif line[:1] in (" ", "+"):
                lines.append(number)
                number += 1
    return found


def post_review(pr: int, review: dict[str, Any]) -> None:
    gh(
        "api",
        f"repos/{{owner}}/{{repo}}/pulls/{pr}/reviews",
        "--input",
        "-",
        "--silent",
        # unescaped, so public() finds a non-ASCII home as GitHub will decode it
        data=public(json.dumps(review, ensure_ascii=False)),
    )


def statuses(head: str) -> list[dict[str, Any]]:
    """The commit statuses on `head`, newest first; ponytail: the first 100, which a head reaches only by hand."""
    out = gh("api", f"repos/{{owner}}/{{repo}}/commits/{head}/statuses?per_page=100")
    found: list[dict[str, Any]] = json.loads(out)
    return found


def post_status(head: str, context: str, description: str, state: str = "success") -> None:
    gh(
        "api",
        f"repos/{{owner}}/{{repo}}/statuses/{head}",
        "-f",
        f"state={state}",
        "-f",
        f"context={context}",
        "-f",
        f"description={description}",
        "--silent",
    )


def issues(numbers: list[int]) -> list[dict[str, Any]]:
    """The issues among `numbers`, as ISSUE reads them, in one call; a number that is a pull request is left out."""
    aliases = " ".join(
        f"i{n}: issueOrPullRequest(number: {n}) {{ ... on Issue {{ {ISSUE} }} }}" for n in numbers
    )
    found = fast(
        lambda: list(
            _graphql(
                f"query($owner: String!, $name: String!) {{ repository(owner: $owner, name: $name) {{ {aliases} }} }}"
            ).values()
        ),
        lambda: [rest_issue(n) for n in numbers],
    )
    return [issue for issue in found if issue]


def default_branch() -> str:
    """The repository's default branch."""
    found: str = fast(
        lambda: gh(
            "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"
        ).strip(),
        lambda: rest("repos/{owner}/{repo}")["default_branch"],
    )
    return found


def ready(number: int, undo: bool = False) -> None:
    """Mark PR #number ready for review, or with `undo` back to draft: over GraphQL, else the draft routes a cloud
    session's proxy serves."""
    fast(
        lambda: gh("pr", "ready", *(("--undo",) if undo else ()), str(number)),
        lambda: gh(
            "api",
            "-X",
            "POST",
            f"repos/{{owner}}/{{repo}}/pulls/{number}/ccr/{'convert_to_draft' if undo else 'ready_for_review'}",
            "--silent",
        ),
    )


def squash_message() -> str:
    """The repo's `squash_merge_commit_message` setting: COMMIT_MESSAGES, PR_BODY or BLANK."""
    found: str = json.loads(gh("api", "repos/{owner}/{repo}"))["squash_merge_commit_message"]
    return found


def pull_commits(number: int) -> list[dict[str, Any]]:
    """PR #number's commits as REST lists them, each with its message and author. ponytail: REST lists the first 250."""
    return [
        json.loads(line)
        for line in gh(
            "api",
            "--paginate",
            f"repos/{{owner}}/{{repo}}/pulls/{number}/commits?per_page=100",
            "--jq",
            ".[]",
        ).splitlines()
    ]


def merge(number: int, method: str, body: str | None, head: str) -> None:
    """Merge PR #number by `method` (merge, squash or rebase), pinned to `head`, with `body` as the commit's body unless
    it is None (GitHub's default). A base requiring a merge queue only queues it."""
    gh(
        "pr",
        "merge",
        str(number),
        f"--{method}",
        *(("--body", body) if body is not None else ()),
        "--match-head-commit",
        head,
    )


def edit_text(method: str, path: str, body: str) -> None:
    """Replace the body of a PR, a comment or a review: `method` (PATCH, or PUT for a review) on the REST `path`
    (`{owner}` and `{repo}` filled by gh), with `body` as the text."""
    gh("api", "-X", method, path, "-f", f"body={body}")


def open_heads() -> list[str]:
    """The head commit of every open PR. ponytail: REST's pages of 100, every one."""
    # whole objects, since rest_pages decodes each line as JSON and a bare SHA is none
    return [pull["head"]["sha"] for pull in rest_pages("pulls?state=open&per_page=100")]


# the GitHub merge queue's calls: enqueue pinned to the head the proofs judged, dequeue a stuck entry
ENQUEUE = (
    "mutation($id: ID!, $head: GitObjectID!) { enqueuePullRequest(input: {pullRequestId: $id, expectedHeadOid: $head})"
    " { mergeQueueEntry { position } } }"
)
DEQUEUE = "mutation($id: ID!) { dequeuePullRequest(input: {id: $id}) { clientMutationId } }"


def enqueue_pull(number: int, node: str, head: str, method: str) -> int | None:
    """Put PR #number (`node`, its GraphQL id) in its base's merge queue pinned to `head`, so GitHub refuses it once
    the head moved: its position, None where GitHub names none. A refusal raises. Where GraphQL answers 403, auto-merge
    on with the queue's merge `method` and `head`, which on a base requiring the queue enqueues it (rest_enqueue)."""

    def graphql() -> int | None:
        out = gh(
            "api", "graphql", "-f", f"query={ENQUEUE}", "-f", f"id={node}", "-f", f"head={head}"
        )
        entry = ((json.loads(out or "{}").get("data") or {}).get("enqueuePullRequest") or {}).get(
            "mergeQueueEntry"
        )
        position: int | None = (entry or {}).get("position")
        return position

    return fast(graphql, lambda: rest_enqueue(number, head, method))


def auto_merge(number: int) -> str:
    """The auto-merge route a cloud session's proxy serves for PR #number."""
    return f"repos/{{owner}}/{{repo}}/pulls/{number}/ccr/auto_merge"


def rest_enqueue(number: int, head: str, method: str) -> None:
    """Auto-merge on for PR #number with `method` (lower case) and `head` as the expected head, then the PR read again:
    a head other than `head` is taken out again and Refused, naming both, since the route may ignore the head it was
    sent. ponytail: a push between the enable and the read that the queue merges before the dequeue lands unseen;
    GitHub drops an entry whose head moves, so that needs a push and a whole `merge_group` run in one REST round trip."""
    gh(
        "api",
        "-X",
        "PUT",
        auto_merge(number),
        "-f",
        f"merge_method={method.lower()}",
        "-f",
        f"expected_head_oid={head}",
        "--silent",
    )
    now = rest(f"repos/{{owner}}/{{repo}}/pulls/{number}")["head"]["sha"]
    if now == head:
        return
    moved = f"its head is {now} now, not {head}, which the proofs judged"
    try:
        gh("api", "-X", "DELETE", auto_merge(number), "--silent")
    except subprocess.CalledProcessError as exc:
        raise Refused(
            f"{moved}, and land could not take it out of the merge queue: take it out on GitHub"
            f" ({' '.join((exc.stderr or '').split())})"
        ) from exc
    raise Refused(f"{moved}: taken out of the merge queue again")


def dequeue_pull(number: int, node: str) -> None:
    """Take PR #number (`node`, its GraphQL id) out of the merge queue: over GraphQL, else auto-merge off."""
    fast(
        lambda: gh("api", "graphql", "-f", f"query={DEQUEUE}", "-f", f"id={node}"),
        lambda: gh("api", "-X", "DELETE", auto_merge(number), "--silent"),
    )


def commit_checks(ref: str) -> dict[str, dict[str, Any]]:
    """The newest run of each check on commit (or branch) `ref`, by name: its conclusion as GraphQL spells it, link and
    id, which for an Actions job is the job's. ponytail: check runs only, one per name; read status contexts and
    workflow names when a queue's required check is a status or one name runs in two workflows."""
    runs = rest_pages(f"commits/{ref}/check-runs?filter=latest&per_page=100", ".check_runs[]")
    return {
        run["name"]: {
            "conclusion": (run.get("conclusion") or "").upper(),
            "url": run.get("html_url") or "",
            "id": run.get("id"),
        }
        for run in runs
    }


def job_log(job: int) -> str:
    """An Actions job's log, by its id, which is its check run's."""
    return gh("api", f"repos/{{owner}}/{{repo}}/actions/jobs/{job}/logs")


def commit_tree(sha: str) -> str:
    """Commit `sha`'s tree SHA."""
    return gh("api", f"repos/{{owner}}/{{repo}}/commits/{sha}", "--jq", ".commit.tree.sha").strip()


def repo_tags(repo: str) -> dict[str, str]:
    """Every tag of `repo`, by name: the commit each points at (an annotated tag's too), from one paged read."""
    out = gh(
        "api", "--paginate", f"repos/{repo}/tags?per_page=100", "--jq", ".[] | [.name, .commit.sha]"
    )
    return {name: sha for name, sha in map(json.loads, out.splitlines())}


def tag_tree(repo: str, tag: str) -> tuple[str, dict[str, tuple[str, str]]] | None:
    """Tag `tag` of `repo`: its commit and the (mode, blob SHA) of every path in that commit's tree; None when the repo
    has no such tag, it names no commit, or GitHub truncates the tree."""
    try:
        found = rest(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    except subprocess.CalledProcessError as exc:
        if "Not Found" in (exc.stderr or ""):
            return None
        raise
    while found["type"] == "tag":  # an annotated tag: its object
        found = rest(f"repos/{repo}/git/tags/{found['sha']}")["object"]
    if found["type"] != "commit":
        return None
    listed = rest(f"repos/{repo}/git/trees/{found['sha']}?recursive=1")
    if listed["truncated"]:
        return None
    return found["sha"], {
        entry["path"]: (entry["mode"], entry["sha"])
        for entry in listed["tree"]
        if entry["type"] != "tree"
    }


def file_at(ref: str, path: str, repo: str | None = None) -> str | None:
    """File `path`'s text at `ref` of `repo` (this checkout's when None); None when it has no such file."""
    try:
        return gh(
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{repo or '{owner}/{repo}'}/contents/{path}?ref={ref}",
        )
    except subprocess.CalledProcessError as exc:
        if "Not Found" in (exc.stderr or ""):
            return None
        raise


class Port:
    """One port's operations, each this module's function of that name, looked up at the call, so a stub set on the
    module (a test's) is the one called."""

    def __init__(self, *operations: str) -> None:
        self.operations = operations

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        if operation not in self.operations:
            raise AttributeError(operation)
        found: Callable[..., Any] = globals()[operation]
        return found


tracker = Port("issue_node", "issues", "comment", "label", "assign", "close_issue")
forge = Port(
    "pull_request",
    "pull_status",
    "current_pr",
    "pr_changes",
    "merged_pull",
    "merge_base",
    "diff_lines",
    "tree",
    "head_pushed",
    "merged_labelled",
    "open_pulls",
    "open_pull_files",
    "open_heads",
    "required_checks",
    "default_branch",
    "squash_message",
    "pull_commits",
    "viewer",
    "writer",
    "github_repo",
    "one_repo",
    "ready",
    "merge",
    "edit_text",
    "enqueue_pull",
    "dequeue_pull",
    "commit_checks",
    "job_log",
    "commit_tree",
    "repo_tags",
    "tag_tree",
    "file_at",
)
evidence = Port("statuses", "post_status", "post_review", "minimize")
