#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""approvals.py: the gatekeeper's former name, kept for one release line. gatekeeper.py beside it holds the CLI and
the policy; its docstring is the manual. Today's verbs run under the same arguments, output and exit codes, the
gatekeeper maps each onto its own (its ALIASES): `approve` is `record approval`, `verdict` is `record
verdict`, `local-ci` is `record checks`, and every other verb is the gatekeeper's own of that name.

This module runs gatekeeper.py's source in its own namespace, so it is the gatekeeper: a name read from it is the
gatekeeper's, and a name set on it (a test's stub) is the one the gatekeeper's code looks up, whether the script
imports it or loads it by path and keeps it out of sys.modules.
"""

import sys
import types
from pathlib import Path

# board.py, which the gatekeeper loads, imports approvals: it reads this module, so it never loads a second copy
_GATEKEEPER = Path(__file__).resolve().with_name("gatekeeper.py")
exec(compile(_GATEKEEPER.read_text(), str(_GATEKEEPER), "exec"), globals())  # noqa: S102 -- the shim is the gatekeeper's own file
# loaded by path: board.py's `import approvals` reads this namespace, not a copy
if sys.modules.get(__name__) is None:
    IMPORTER = types.ModuleType("approvals")

    def _read(name: str) -> object:
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(name) from None

    IMPORTER.__getattr__ = _read
