// Prints the Code Mode guide for a launcher's --append-system-prompt: bun guide.ts [exclusive|preferred].
// The launcher also sets CODE_MODE_GUIDE=system, so repl's description points here instead of repeating it.
import { section } from "./hooks/register.ts";

process.stdout.write(section(process.argv[2] === "preferred" ? "preferred" : "exclusive"));
