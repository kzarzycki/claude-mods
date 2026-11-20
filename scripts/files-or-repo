#!/usr/bin/env bash
# Run a linter on the files given after the last `--`, or on every tracked file when none are given.
# A `lint:` task calls it, so the git hook (staged files) and `mise run check:lint` (the whole
# repo) run one command on the same selection.
#
#   files-or-repo [--only ERE] [--skip ERE] [--text] [--fixer] COMMAND [ARG...] -- [FILE...]
#
#   --only ERE   keep the paths that match
#   --skip ERE   drop the paths that match
#   --text       keep text files (no NUL byte), as pre-commit's `types: [text]`
#   --fixer      fail when COMMAND changed a file, as pre-commit does with a fixer that exits 0
set -euo pipefail

only="" skip="" text=false fixer=false
while [ $# -gt 0 ]; do
  case "$1" in
    --only) only="$2"; shift 2 ;;
    --skip) skip="$2"; shift 2 ;;
    --text) text=true; shift ;;
    --fixer) fixer=true; shift ;;
    *) break ;;
  esac
done

# The last `--` ends the command, so a command may hold a `--` of its own.
last=0 i=0
for arg in "$@"; do
  i=$((i + 1))
  [ "$arg" = -- ] && last=$i
done
[ "$last" -gt 1 ] || { echo "usage: files-or-repo [options] COMMAND [ARG...] -- [FILE...]" >&2; exit 2; }
command=("${@:1:last-1}")
shift "$last"

list="$(mktemp)"
trap 'rm -f "$list" "$list.picked" "$list.before" "$list.after"' EXIT
if [ $# -gt 0 ]; then printf '%s\0' "$@" >"$list"; else git ls-files -z >"$list"; fi

# One grep per filter over the whole list, NUL-separated, so a path may hold spaces or quotes.
# $1 is -v to drop the matches; grep exits 1 when nothing is left, which is no error.
pick() { if [ -n "$2" ]; then grep -zE $1 -- "$2" || true; else cat; fi; }
# Regular files only: a symlink is lint:symlinks', and a tracked file deleted in the tree has nothing to lint.
pick "" "$only" <"$list" | pick -v "$skip" | while IFS= read -r -d '' path; do
  if [ -f "$path" ] && [ ! -L "$path" ]; then printf '%s\0' "$path"; fi
done >"$list.picked"
if [ "$text" = true ] && [ -s "$list.picked" ]; then
  # grep -I treats a binary file as matching nothing, and an empty file has no line to match.
  xargs -0 grep -Il --null -- '' <"$list.picked" >"$list" || true
  mv "$list" "$list.picked"
fi
[ -s "$list.picked" ] || exit 0

hashes() { tr '\0' '\n' <"$list.picked" | git hash-object --stdin-paths; }
[ "$fixer" = false ] || hashes >"$list.before"
status=0
xargs -0 "${command[@]}" <"$list.picked" || status=$?
if [ "$fixer" = true ]; then
  hashes >"$list.after"
  if ! cmp -s "$list.before" "$list.after"; then
    echo "files-or-repo: ${command[0]} changed files; review and stage them" >&2
    [ "$status" -ne 0 ] || status=1
  fi
fi
exit "$status"
