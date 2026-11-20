"""folding.py: the one shape every comment the loop writes takes: a heading line a parser reads, a short human
summary (at most about three lines in GitHub's UI), and the rest folded under `<details>`.

    <heading>
    <summary lines>

    <details><summary>Details</summary>

    <machine lines>

    </details>

`machine(body)` is what a parser reads: the heading, then the folded lines in the place they were before folding
(`Head:`, `By:`, `Approved:` records), with the summary and the fold's markup left out. A body with no fold is
returned as it is, so comments posted before folding read the same.
"""

import re

LABEL = "Details"
# the fold fold() writes (one level: a second fold goes after it, never inside it)
_FOLD = re.compile(
    rf"\n*<details><summary>{LABEL}</summary>\n\n(.*?)\n*</details>[ \t]*(?:\n|\Z)", re.DOTALL
)


def fold(heading: str, summary: str = "", details: str = "") -> str:
    """`heading`, the human `summary` under it, and `details` folded after them; no fold when there are no details."""
    top = heading + ("\n" + summary.strip("\n") if summary else "")
    if not details.strip():
        return top + "\n"
    return (
        f"{top}\n\n<details><summary>{LABEL}</summary>\n\n{details.strip(chr(10))}\n\n</details>\n"
    )


def machine(body: str) -> str:
    """The body as a parser reads it: first line, then the folded lines in place of the summary; an unfolded body
    as it is."""
    found = _FOLD.search(body)
    if not found:
        return body
    first, rest = body.lstrip().split("\n", 1)[0], body[found.end() :].lstrip("\n")
    return first + "\n" + found[1] + ("\n\n" + rest if rest.strip() else "\n")


def visible(body: str) -> str:
    """The body as a person reads it before opening the fold: the heading and the summary, with the folded lines gone."""
    return _FOLD.sub("", body)
