// TTSR rule files: Markdown with a frontmatter block, the same format oh-my-pi reads.
//
//   ---
//   description: No `any` in TypeScript
//   condition: ":\s*any\b"
//   scope: tool:edit(*.ts)
//   globs: ["src/**"]
//   ---
//   Use `unknown` and narrow it instead of `any`.
//
// `condition` is a regex checked against what a tool is about to write or run.
// `question` is a yes/no question the judge answers about each finished turn.
// A rule with neither is not a TTSR rule and is skipped.

export type Rule = {
  name: string;
  source: string;
  description: string;
  body: string;
  condition?: RegExp;
  question?: string;
  /** Tool names the condition applies to; empty means every tool. */
  tools: string[];
  /** Path globs from the scope, e.g. `tool:edit(*.ts)`; the file must match one when present. */
  scopeGlobs: RegExp[];
  /** Path globs from `globs:`; the file must also match one of these when present. */
  globs: RegExp[];
  enabled: boolean;
};

// ponytail: a flat YAML subset (key: value, inline [a, b] lists, "- item" lists, quoted strings).
// Enough for rule frontmatter; nested maps are ignored. Upgrade path: bundle a YAML parser.
export function parseFrontmatter(text: string): { data: Record<string, unknown>; body: string } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text);
  if (!m) return { data: {}, body: text.trim() };
  const data: Record<string, unknown> = {};
  let listKey: string | undefined;
  for (const raw of m[1]!.split(/\r?\n/)) {
    const item = /^\s+-\s+(.*)$/.exec(raw);
    if (item && listKey) {
      (data[listKey] as unknown[]).push(scalar(item[1]!));
      continue;
    }
    const kv = /^([A-Za-z_][\w-]*)\s*:\s*(.*)$/.exec(raw);
    if (!kv) continue;
    const key = kv[1]!;
    const value = kv[2]!;
    if (value === "") {
      data[key] = [];
      listKey = key;
    } else {
      listKey = undefined;
      data[key] = /^\[.*\]$/.test(value) ? splitList(value.slice(1, -1)).map(scalar) : scalar(value);
    }
  }
  return { data, body: m[2]!.trim() };
}

function splitList(s: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quote = "";
  for (const ch of s) {
    if (quote) {
      cur += ch;
      if (ch === quote) quote = "";
    } else if (ch === '"' || ch === "'") {
      quote = ch;
      cur += ch;
    } else if (ch === ",") {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

function scalar(v: string): string | boolean | number {
  const s = v.trim();
  if (/^".*"$/.test(s)) return s.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  if (/^'.*'$/.test(s)) return s.slice(1, -1).replace(/''/g, "'");
  if (s === "true") return true;
  if (s === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
  return s;
}

/** Glob to regex: `**` crosses directories, `*` and `?` don't, `{a,b}` alternates. */
export function globToRegExp(glob: string): RegExp {
  let re = "";
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i]!;
    if (c === "*" && glob[i + 1] === "*") {
      re += glob[i + 2] === "/" ? "(?:.*/)?" : ".*";
      i += glob[i + 2] === "/" ? 2 : 1;
    } else if (c === "*") re += "[^/]*";
    else if (c === "?") re += "[^/]";
    else if (c === "{") {
      const end = glob.indexOf("}", i);
      re += `(?:${glob.slice(i + 1, end).split(",").map(escape).join("|")})`;
      i = end;
    } else re += escape(c);
  }
  // A glob without a slash matches the file name anywhere, like .gitignore.
  return new RegExp(glob.includes("/") ? `^${re}$` : `(?:^|/)${re}$`);
}
const escape = (s: string) => s.replace(/[.+^$()|[\]\\]/g, "\\$&");

// omp names tools in lower case; map them to Claude Code's.
const TOOL_ALIASES: Record<string, string[]> = {
  edit: ["Edit", "MultiEdit", "NotebookEdit"],
  write: ["Write"],
  bash: ["Bash"],
  read: ["Read"],
};

/** `tool`, `tool:edit`, `tool:edit(*.ts)`, `tool:edit,write(src/**)`; `text`/`thinking` aren't checkable here. */
function parseScope(scope: unknown): { tools: string[]; globs: string[]; streamOnly: boolean } {
  const parts = (Array.isArray(scope) ? scope : scope ? [scope] : []).map(String);
  if (parts.length === 0) return { tools: [], globs: [], streamOnly: false };
  const tools: string[] = [];
  const globs: string[] = [];
  let toolScoped = false;
  for (const p of parts) {
    const m = /^tool(?::([^()]+))?(?:\(([^)]*)\))?$/.exec(p.trim());
    if (!m) continue;
    toolScoped = true;
    for (const t of (m[1] ?? "").split(",").map(s => s.trim()).filter(Boolean)) tools.push(...(TOOL_ALIASES[t.toLowerCase()] ?? [t]));
    if (m[2]) globs.push(...m[2].split(",").map(s => s.trim()));
  }
  return { tools, globs, streamOnly: !toolScoped };
}

export function parseRule(name: string, source: string, text: string): Rule | undefined {
  const { data, body } = parseFrontmatter(text);
  const cond = data.condition ?? data.ttsr_trigger;
  const question = typeof data.question === "string" ? data.question : undefined;
  if (cond === undefined && !question) return undefined;
  const scope = parseScope(data.scope);
  // A condition scoped only to streamed text/thinking can't be checked from tool calls; keep the rule
  // for its question (if any) and drop the condition.
  let condition: RegExp | undefined;
  if (cond !== undefined && !scope.streamOnly) {
    try {
      condition = new RegExp(String(cond), "m");
    } catch {
      condition = undefined;
    }
  }
  if (!condition && !question) return undefined;
  const globList = Array.isArray(data.globs) ? data.globs.map(String) : typeof data.globs === "string" ? [data.globs] : [];
  return {
    name,
    source,
    description: String(data.description ?? ""),
    body,
    condition,
    question,
    tools: scope.tools,
    scopeGlobs: scope.globs.map(globToRegExp),
    globs: globList.map(globToRegExp),
    enabled: data.enabled !== false,
  };
}

/** The text a tool is about to write or run, which conditions are checked against. */
export function toolPayload(tool: string, input: Record<string, unknown>): { text: string; path?: string } {
  const path = typeof input.file_path === "string" ? input.file_path : typeof input.notebook_path === "string" ? input.notebook_path : undefined;
  switch (tool) {
    case "Write":
      return { text: String(input.content ?? ""), path };
    case "Edit":
      return { text: String(input.new_string ?? ""), path };
    case "MultiEdit":
      return { text: ((input.edits as { new_string?: string }[]) ?? []).map(e => e.new_string ?? "").join("\n"), path };
    case "NotebookEdit":
      return { text: String(input.new_source ?? ""), path };
    case "Bash":
      return { text: String(input.command ?? "") };
    default:
      return { text: JSON.stringify(input), path };
  }
}

/** The first enabled rule whose condition matches this tool call. */
export function matchToolRule(rules: Rule[], tool: string, input: Record<string, unknown>, cwd = ""): { rule: Rule; match: string } | undefined {
  const { text, path } = toolPayload(tool, input);
  const rel = path && cwd && path.startsWith(`${cwd}/`) ? path.slice(cwd.length + 1) : path;
  for (const rule of rules) {
    if (!rule.enabled || !rule.condition) continue;
    if (rule.tools.length && !rule.tools.includes(tool)) continue;
    if (rule.scopeGlobs.length && (!rel || !rule.scopeGlobs.some(g => g.test(rel)))) continue;
    if (rule.globs.length && (!rel || !rule.globs.some(g => g.test(rel)))) continue;
    const m = rule.condition.exec(text);
    if (m) return { rule, match: m[0] };
  }
  return undefined;
}
