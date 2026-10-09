#!/usr/bin/env bash
# Run every e2e check (or the ones named: `e2e/run.sh eval ttsr`). Costs real model calls.
cd "$(dirname "$0")"
failed=0
for name in ${@:-decision eval ttsr compact hub self-compact}; do
  echo "== $name"
  bash "./$name.sh" || failed=$((failed + 1))
done
echo "== $failed check file(s) failed"
exit $failed
