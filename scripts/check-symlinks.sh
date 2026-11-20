#!/usr/bin/env bash
# Reject a symlink whose target does not resolve, or is absolute and so resolves only on
# this machine. Checks the given paths (the git hook passes staged symlinks), or every
# tracked file when given none.
set -eu
fail=0
check() {
  [ -L "$1" ] || return 0
  target="$(readlink "$1")"
  case "$target" in
    /*) printf 'absolute symlink: %s -> %s\n' "$1" "$target" >&2; fail=1 ;;
    *) [ -e "$1" ] || { printf 'dangling symlink: %s -> %s\n' "$1" "$target" >&2; fail=1; } ;;
  esac
}
if [ $# -gt 0 ]; then
  for f in "$@"; do check "$f"; done
else
  while IFS= read -r -d '' f; do check "$f"; done < <(git ls-files -z)
fi
exit "$fail"
