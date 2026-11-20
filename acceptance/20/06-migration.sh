#!/usr/bin/env bash
# Story: the README tells an eval-kernel user to uninstall it before installing code-mode.
grep -q 'claude plugin uninstall eval-kernel@claude-mods' README.md || { echo "README: no eval-kernel uninstall step"; exit 1; }
grep -q 'claude plugin install code-mode@claude-mods' README.md || { echo "README: no code-mode install step"; exit 1; }
echo "README names the uninstall and install steps"
