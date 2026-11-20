#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""approvals.py: the gatekeeper's former name, kept for one release line. gatekeeper.py beside it holds the CLI and
the policy; its docstring is the manual. Today's verbs run under the same arguments, output and exit codes, each
mapped onto the gatekeeper's (gatekeeper.py's ALIASES): `approve` is `record approval`, `verdict` is `record
verdict`, `local-ci` is `record checks`, and every other verb is the gatekeeper's own of that name.

Imported, this module is the gatekeeper itself: every name read from it is gatekeeper.py's, and every name set on it
(a test's stub) is set there, so a script that imports approvals reads and patches the code that runs. A module loaded
by path and kept out of sys.modules reads the gatekeeper's names, but a name set on it stays its own.
"""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


def _load() -> types.ModuleType:
    """gatekeeper.py beside this file, loaded by path under its own name, so two copies in one process (a project's
    and an installed one) each load their own and none is found on sys.path by accident."""
    spec = importlib.util.spec_from_file_location(
        f"{__name__}_gatekeeper", Path(__file__).resolve().with_name("gatekeeper.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GATEKEEPER = _load()
# board.py, which the gatekeeper loads, imports approvals: it reads this module, not a second copy
_GATEKEEPER.IMPORTER = sys.modules.get(__name__)


class _Alias(types.ModuleType):
    """This module as the gatekeeper: a name it lacks is read from gatekeeper.py and every name set is set there."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_GATEKEEPER, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") and name.endswith("__"):  # the import machinery's own
            super().__setattr__(name, value)
        else:
            setattr(_GATEKEEPER, name, value)

    def __delattr__(self, name: str) -> None:
        delattr(_GATEKEEPER, name)


def __getattr__(name: str) -> Any:
    """A name this module lacks, read from gatekeeper.py, where a loader keeps the module out of sys.modules."""
    return getattr(_GATEKEEPER, name)


if __name__ == "__main__":
    sys.exit(_GATEKEEPER.cli(_GATEKEEPER.aliased(sys.argv[1:])))

# an import: a name set on this module is set on the gatekeeper too
if __name__ in sys.modules:
    sys.modules[__name__].__class__ = _Alias
