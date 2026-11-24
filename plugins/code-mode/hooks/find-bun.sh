#!/bin/sh
# The one lookup for bun. Prints the path of the bun to run and exits 0, or prints nothing and exits 1.
# Order: $BUN_INSTALL/bin, then PATH, then ~/.bun/bin, then /opt/homebrew/bin.
# Used by the mod (hooks/register.ts, to start the kernel) and by session-start.sh.
if [ -n "${BUN_INSTALL:-}" ] && [ -x "$BUN_INSTALL/bin/bun" ]; then echo "$BUN_INSTALL/bin/bun"; exit 0; fi
if p=$(command -v bun 2>/dev/null) && [ -x "$p" ]; then echo "$p"; exit 0; fi
for d in "${HOME:-}/.bun/bin" /opt/homebrew/bin; do
  if [ -x "$d/bun" ]; then echo "$d/bun"; exit 0; fi
done
exit 1
