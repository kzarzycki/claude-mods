#!/usr/bin/env bash
# Fast checks, no model calls: validate, unit-test and type-check every mod, then the eval kernel's
# self-check. The e2e checks (real sessions, real model calls) are e2e/run.sh.
cd "$(dirname "$0")/.."
failed=0
step() { local name=$1; shift; if "$@" > /tmp/cm-check.out 2>&1; then echo "ok   $name"; else echo "FAIL $name"; sed 's/^/     /' /tmp/cm-check.out | tail -30; failed=$((failed + 1)); fi; }
for p in plugins/*/; do
  p=${p%/}
  step "$p validate" claude plugin validate "$p"
  step "$p test" claude plugin test "$p"
  # The engine lays the types into .claude-plugin/types the first time it loads the mod.
  if [ -d "$p/.claude-plugin/types" ]; then step "$p tsc" bunx -p typescript tsc -p "$p"; else echo "skip $p tsc (load it once with claude --plugin-dir $p to lay its types)"; fi
done
step "cm-eval kernel self-check" bun plugins/cm-eval/kernel/kernel.check.ts
echo "$failed failed"
exit $failed
