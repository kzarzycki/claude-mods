#!/usr/bin/env bash
# Record and post a PR demo: render each `.tape` with VHS, convert each `.webm` or `.mov` to H.264
# MP4, take each `.mp4` as is, and post them all in one `## Demo` comment with `gh pr comment
# --attach`, so every video plays inline. A `.png` or `.jpg` is attached as it is, for a change
# with nothing moving. Earlier `## Demo` comments by the same poster are
# minimized as outdated. Every refusal runs before anything records.
# Usage: demo.sh [--pr <number>] [--caption "<what it shows>"] <recording>...
set -euo pipefail

usage() { echo 'usage: demo.sh [--pr <number>] [--caption "<what it shows>"] <recording>...' >&2; exit 2; }

pr="" caption=""
while [ $# -gt 0 ]; do
  case "$1" in
    --pr) [ $# -ge 2 ] && [[ $2 =~ ^[0-9]+$ ]] || usage; pr="$2"; shift 2 ;;
    --caption) [ $# -ge 2 ] && [ -n "$2" ] || usage; caption="$2"; shift 2 ;;
    --) shift; break ;;
    -*) usage ;;
    *) break ;;
  esac
done
[ $# -ge 1 ] || usage

tapes=0
for recording in "$@"; do
  [ -s "$recording" ] || { echo "demo: $recording is missing or empty" >&2; exit 2; }
  case "$recording" in
    *.tape) tapes=1 ;;
    *.webm | *.mov | *.mp4 | *.png | *.jpg) ;;
    *) echo "demo: $recording is not a .tape, .webm, .mov, .mp4, .png or .jpg" >&2; exit 2 ;;
  esac
done

# --attach arrived in gh 2.99.0; an older gh would fail only after the recording.
version="$(gh --version | sed -nE '1s/^gh version ([0-9]+)\.([0-9]+).*/\1 \2/p')"
read -r major minor <<<"${version:-0 0}"
if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 99 ]; }; then
  echo "demo: gh $major.$minor cannot attach a video to a comment; upgrade gh to 2.99.0 or later, else stop and report: a video posted another way (a release asset, a link) downloads instead of playing, and check merge refuses it" >&2
  exit 1
fi
if [ "$tapes" = 1 ] && ! command -v ttyd >/dev/null; then
  echo "demo: VHS needs ttyd on PATH to render a tape; install it" >&2
  exit 1
fi

# With several GitHub remotes and no `gh repo set-default`, gh reads the PR as `upstream`'s: refuse rather than
# post to a repo nobody chose.
repos="$(git remote -v | awk '{print $2}' | sed -E 's#/+$##; s#\.git/*$##' |
  sed -nE 's#^([a-zA-Z][a-zA-Z0-9+.-]*://)?([^@/]*@)?([^/:]+)(:[0-9]+)?[:/]/*([^/]+/[^/]+)$#\3 \5#p' |
  awk 'tolower($1) == "github.com" { print tolower($2) }' | sort -u)"
if [ "$(printf '%s' "$repos" | grep -c .)" -gt 1 ] && ! git config --get-regexp '^remote\..*\.gh-resolved$' >/dev/null; then
  echo "demo: this checkout's remotes name $(echo $repos) and gh has no default among them: run gh repo set-default <owner>/<repo>" >&2
  exit 1
fi

pr="${pr:-$(gh pr view --json number --jq .number)}"
head="$(git rev-parse HEAD)"
pr_head="$(gh pr view "$pr" --json headRefOid --jq .headRefOid)"
if [ "$head" != "$pr_head" ]; then
  echo "demo: this checkout is at ${head:0:7}, PR #$pr's head is ${pr_head:0:7}; record from a clean checkout of the head" >&2
  exit 3
fi
# --untracked-files=all whatever status.showUntrackedFiles says: an untracked module a committed
# one imports records fine here and fails for everyone else.
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  echo "demo: this checkout has uncommitted or untracked files, so the video may not show PR #$pr's head; commit and push them, or remove them" >&2
  exit 3
fi

staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
attach=() names=""
i=0
for recording in "$@"; do
  i=$((i + 1))
  video="$staging/pr$pr-${head:0:7}-$i.mp4"
  case "$recording" in *.png | *.jpg) video="$staging/pr$pr-${head:0:7}-$i.${recording##*.}" ;; esac
  case "$recording" in
    *.tape) vhs "$recording" -o "$video" ;;
    *.webm | *.mov) ffmpeg -loglevel error -y -i "$recording" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "$video" ;;
    *.mp4 | *.png | *.jpg) cp "$recording" "$video" ;;
  esac
  [ -s "$video" ] || { echo "demo: $recording produced no file" >&2; exit 1; }
  attach+=(--attach "$video")
  names+="${names:+, }$(basename "$recording")"
done

# Read your earlier demos before posting, so the new comment is not among them; a
# reviewer's own `## Demo` comment is left alone.
me="$(gh api user --jq .login)"
old="$(gh api "repos/{owner}/{repo}/issues/$pr/comments" --paginate \
  --jq ".[] | select(.user.login == \"$me\" and (.body | startswith(\"## Demo\"))) | .node_id")"

gh pr comment "$pr" --body "## Demo

${caption:-$names}, on ${head:0:7}." "${attach[@]}"

for id in $old; do
  # shellcheck disable=SC2016  # $id is a GraphQL variable, not a shell one.
  gh api graphql -f query='mutation($id: ID!) { minimizeComment(input: {subjectId: $id, classifier: OUTDATED}) { clientMutationId } }' \
    -f id="$id" >/dev/null || echo "demo: posted, but could not minimize $id" >&2
done
