// The manifest names an author, so `claude plugin validate` has nothing to warn about.
// Plain bun, not `claude plugin test`: that sandbox reads no files.
import { readFileSync } from "node:fs";

const manifest = JSON.parse(readFileSync(new URL("../.claude-plugin/plugin.json", import.meta.url), "utf8"));
if (!manifest.author?.name) {
  console.error("plugin.json has no author.name");
  process.exit(1);
}
console.log(`author: ${manifest.author.name}`);
