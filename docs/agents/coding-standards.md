# Coding standards

The `engineering-loop` skill reads this file at Build and Verify. The pack's
generic standards and the language toolchain's checks are not restated here:
this file holds only facts about this project's domain that change the code.
Add a line on the second occurrence of a mistake; delete a line that would not
change behaviour.

## Domain facts

- The engine requires each environment read to be a literal `$.env.get("NAME")`; a name built at
  run time doesn't work.
- Claude Code's deny rules and `--disallowedTools` don't bind a mod's `$.tool.call`: hiding a tool
  from the model leaves it callable by the mod.
- An organization's managed mod can skip a person's `prompt.compose`, `prompt.section` and
  `prompt.context` hooks; text the model must see goes through a hook that isn't skipped, such as
  `tool.describe`.
- A session started from inside another Claude Code session inherits `CLAUDE_CODE_CHILD_SESSION` and
  saves no transcript; e2e scripts unset it.
- `claude plugin test` can't route one mod's call to another mod's noun on 2.1.321 to 2.1.326; a test
  that needs it skips there and says so, and e2e covers it.
