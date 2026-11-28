// code-mode kernel: a long-lived Bun process that keeps a repl's JavaScript state between calls.
//
// It serves HTTP on a Unix socket because a mod can't hold a child's stdin open across calls.
// A script that needs the host (a Claude Code tool, a model, a subagent) does not reach Claude Code
// itself: it parks the call and hands it back to the mod as a `call` event; the mod runs it and
// answers with /resume. Every host call therefore goes through Claude Code's permissions and hooks.
//
//   POST /run     { code, cwd? }                  -> Event & { cell }  (start a script; cell names it)
//   POST /resume  { callId, ok, value?, error? }  -> Event   (answer a call, then that script's next event)
//   POST /answer  { callId, ok, value?, error? }  -> { ok }  (answer a call without waiting)
//   POST /next    { cell }                        -> Event   (that script's next event)
//   POST /cancel  { cell }                        -> { ok }  (stop a script: its host calls reject from now on)
//   POST /reset                                   -> exits; the mod starts a fresh kernel
//   GET  /health, GET /vars
//
// Several scripts may run at once, in one shared global scope: a subagent's script sees the
// variables its parent's script made, and the other way round. Each script is a cell with its own
// event queue; AsyncLocalStorage tells which cell a host call or a log line belongs to.
//
// /answer + /next let a call be answered out of band: the mod answers a subagent's call from the
// subagent's own turn.complete hook while the repl hook waits on /next, so every wait the repl
// hook does is inside $.http.fetch, which its hook budget doesn't count.
//
// Event = { status: "call", callId, kind, payload }
//       | { status: "wait" }                     (nothing new for WAIT_MS: ask /next again)
//       | { status: "done", output, value? }
//       | { status: "error", output, error }
//
// "wait" keeps each HTTP request short: a request open longer than about 30 s is cut by the host,
// so a script may run as long as it likes as long as the mod keeps asking.

import { AsyncLocalStorage } from "node:async_hooks";
import { existsSync, unlinkSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

type Event =
  | { status: "call"; callId: string; kind: string; payload: unknown }
  | { status: "wait" }
  | { status: "done"; output: string; value?: string }
  | { status: "error"; output: string; error: string };

/** Each part of a result (a returned key, the log) is cut to PART characters, head and tail kept. */
const PART = 20_000;
const MAX_OUTPUT = 50_000;
const socket = process.argv[2];
const WAIT_MS = Number(process.argv[3] ?? 20_000);
/** A file whose existence means an earlier kernel of this session already ran a script. */
const marker = process.argv[4];
if (!socket) throw new Error("usage: bun kernel.ts <socket path> [wait ms] [marker file]");

// ---- cells: one per running script, each an event queue the HTTP handlers pull from ----

class Cell {
  events: Event[] = [];
  waiter: ((e: Event) => void) | undefined;
  output: string[] = [];
  /** Set once the script ended or was cancelled: its host calls reject, later events are dropped. */
  ended = false;
  /** The script's last event (done or error) is queued; nothing after it is. */
  final = false;
  constructor(public id: string, public cwd: string) {}
  push(e: Event) {
    if (this.final) return;
    if (e.status === "done" || e.status === "error") this.final = true;
    if (this.waiter) this.waiter(e);
    else this.events.push(e);
  }
  /** The next event, or "wait" after ms. A wait unhooks its waiter in the same tick, so an event
   *  pushed after it stays queued for the following caller instead of resolving a promise nobody reads. */
  next(ms: number): Promise<Event> {
    const e = this.events.shift();
    if (e) return Promise.resolve(e);
    return new Promise(r => {
      const timer = setTimeout(() => {
        this.waiter = undefined;
        r({ status: "wait" });
      }, ms);
      this.waiter = ev => {
        clearTimeout(timer);
        this.waiter = undefined;
        r(ev);
      };
    });
  }
}

const cells = new Map<string, Cell>();
const current = new AsyncLocalStorage<Cell>();
const pending = new Map<string, { cell: Cell; resolve: (v: unknown) => void; reject: (e: Error) => void }>();
/** Calls a cell left unanswered when it ended: a late answer to one is dropped, not refused. */
const cancelled = new Set<string>();
let callSeq = 0, cellSeq = 0;
/** This kernel's generation, in every call and cell id: the supervisor restarts the kernel on the same
 *  socket, and a late answer meant for a script of the earlier kernel must not reach a new one. */
const GEN = `${process.pid.toString(36)}${Date.now().toString(36)}`;
const mine = (id: string) => id.startsWith(`${GEN}.`);

function host(kind: string, payload: unknown): Promise<any> {
  const c = current.getStore();
  if (!c) return Promise.reject(new Error("host calls are only available while a script runs"));
  if (c.ended) return Promise.reject(new Error("the script was stopped or has ended"));
  const callId = `${GEN}.c${++callSeq}`;
  return new Promise((res, rej) => {
    pending.set(callId, { cell: c, resolve: res, reject: rej });
    c.push({ status: "call", callId, kind, payload });
  });
}

/** End a cell: queued calls are dropped and pending ones rejected, so its last event comes next. */
function end(c: Cell, why: string) {
  c.ended = true;
  c.events = c.events.filter(e => e.status !== "call");
  for (const [id, p] of pending) {
    if (p.cell !== c) continue;
    pending.delete(id);
    cancelled.add(id);
    p.reject(new Error(why));
  }
}

function show(v: unknown): string {
  if (typeof v === "string") return v;
  if (v instanceof ShellOutput) return [v.output, v.note && `[note] ${v.note}`].filter(Boolean).join("\n");
  if (v instanceof Error) return v.stack ?? String(v);
  if (v === undefined) return "undefined";
  try {
    return JSON.stringify(v, null, 2) ?? String(v);
  } catch {
    return String(v);
  }
}

function write(line: string) {
  current.getStore()?.output.push(line);
}

// ---- the prelude: Code Mode's globals ($, file, edit, write, preview, tools, ...) plus agent(),
// completion() and judge(). Shell and file work goes through Claude Code's own tools (Bash, Read,
// Edit, Write) as host calls, so hooks see it and the person sees each call.

const g = globalThis as any;
const nativeConsole = { log: console.log, error: console.error, warn: console.warn, info: console.info };
/** Paths resolve from the cwd of the script's own /run (its session's or subagent's). */
const abs = (p: string) => resolve(current.getStore()?.cwd ?? process.cwd(), p);

/** self.log / log: a line delivered with the result. */
g.log = (...a: unknown[]) => write(a.map(show).join(" "));

/** console.*: a bounded ring kept out of the result; console.tail(n) reads it back. */
const RING = 1000;
const ring: string[] = [];
let ringDropped = 0;
const toRing = (...a: unknown[]) => {
  ring.push(a.map(show).join(" "));
  if (ring.length > RING) (ring.shift(), ringDropped++);
};
Object.assign(console, {
  log: toRing, info: toRing, debug: toRing, warn: toRing, error: toRing,
  tail: (n = 20) => ring.slice(-n).join("\n"),
  buffer: () => ring.join("\n"),
  dropped: () => ringDropped,
});

// A promise a script let go of (a call it never awaited) must not end the kernel and every
// variable in it, which is what Bun does with an unhandled rejection by default.
process.on("unhandledRejection", e => toRing(`unhandled rejection: ${show(e)}`));
process.on("uncaughtException", e => toRing(`uncaught exception: ${show(e)}`));

// A script that exits the process ends the kernel and every variable in it. The kernel's own exits
// (/reset, SIGTERM) use realExit; scripts get an error that says what to do instead.
const realExit = process.exit.bind(process);
const noExit = (what: string) => () => {
  throw new Error(`${what} would end the kernel and every variable in it. Throw an error to stop the script; pass reset: true to restart the kernel on purpose.`);
};
process.exit = noExit("process.exit()") as typeof process.exit;
process.abort = noExit("process.abort()") as typeof process.abort;

g.sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

// ---- tools ----

/** A built-in resolves {error} on failure; an MCP tool throws. */
async function callTool(name: string, input: object = {}) {
  const r = await host("tool", { tool: name, args: input });
  if (!r?.isError) return r?.result ?? r?.text;
  if (name.startsWith("mcp__")) {
    const err: any = new Error(r.text ?? "MCP tool failed");
    err.name = "McpToolError";
    try { err.detail = JSON.parse(r.text); } catch {}
    throw err;
  }
  return { error: r.text ?? "tool failed" };
}
g.tools = new Proxy({}, {
  get: (_t, name: string) => {
    if (name === "then") return undefined; // so `await tools` doesn't hang
    if (name === "list") return async () => ((await host("tools", {})) as { name: string }[]).map(t => t.name);
    return (input: object) => callTool(name, input);
  },
});

/** First sentence, as Code Mode's `about`. */
const about = (d: string) => (d.match(/^[\s\S]*?[.!?](\s|$)/)?.[0] ?? d).trim().slice(0, 300);

g.searchTools = async (query: string, max = 10) => {
  const words = String(query ?? "").toLowerCase().split(/\W+/).filter(Boolean);
  if (!words.length) return { error: "searchTools needs a query" };
  const list = (await host("tools", {})) as { name: string; description: string }[];
  return list
    .map(t => {
      const name = t.name.toLowerCase(), desc = (t.description ?? "").toLowerCase();
      return { t, score: words.reduce((s, w) => s + (name.includes(w) ? 3 : 0) + (desc.includes(w) ? 1 : 0), 0) };
    })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, max)
    // ponytail: no input types, since Claude Code gives mods no tool schemas. Upgrade path: read
    // them from the types the engine lays in .claude-plugin/types when it loads the mod.
    .map(({ t }) => ({ name: t.name, about: about(t.description ?? ""), input: "unknown: see describeTool(name)" }));
};
g.describeTool = async (name: string) => {
  const t = ((await host("tools", {})) as { name: string; description: string }[]).find(x => x.name === name);
  return t ? { name: t.name, description: t.description } : { error: `describeTool: no tool named ${name}` };
};

// ---- the shell: $ runs each command as one Bash tool call ----

const quote = (s: string) => `'${s.replace(/'/g, `'\\''`)}'`;
function word(v: unknown): string {
  if (Array.isArray(v)) return v.map(word).join(" ");
  if (v && typeof v === "object" && "raw" in v) return String((v as { raw: unknown }).raw);
  return quote(String(v));
}
/** An exit 1 from these commands is their answer (no match, files differ), not a failure. */
const ANSWERS_WITH_1 = /(?:^|[|;&]\s*)(?:grep|egrep|fgrep|rg|find|diff|test|\[|git\s+diff|git\s+grep)\b[^|;&]*$/;

class ShellOutput {
  stderr = "";
  truncated = false;
  whole = true;
  constructor(public stdout: string, public exitCode: number | null, public error?: string, public note?: string) {}
  text() { return this.stdout; }
  lines() { const s = this.stdout.replace(/\n$/, ""); return s ? s.split("\n") : []; }
  json() { return JSON.parse(this.stdout); }
  get output() {
    return [this.stdout, this.error && `[error] ${this.error}`, this.exitCode ? `[exit ${this.exitCode}]` : ""].filter(Boolean).join("\n");
  }
  toJSON() { return { exitCode: this.exitCode, output: this.output, ...(this.note ? { note: this.note } : {}) }; }
}
class ShellError extends Error {
  stdout: string; stderr = ""; exitCode: number | null; truncated = false;
  constructor(out: ShellOutput) {
    super(`ShellError: exit ${out.exitCode}:\n${out.output.slice(-4000)}`);
    this.name = "ShellError";
    this.stdout = out.stdout;
    this.exitCode = out.exitCode;
  }
}

async function runShell(cmd: string, o: { throws: boolean; timeout?: number; cwd?: string; env?: Record<string, string> }) {
  const env = Object.entries(o.env ?? {}).map(([k, v]) => `export ${k}=${quote(v)}; `).join("");
  const dir = `cd ${quote(abs(o.cwd ?? "."))} && `;
  const command = `(${env}${dir}${cmd}\n)`;
  const r = await host("tool", { tool: "Bash", args: { command, description: cmd.split("\n")[0]!.slice(0, 80), ...(o.timeout ? { timeout: o.timeout } : {}) } });
  let out: ShellOutput;
  if (!r?.isError) out = new ShellOutput(String(r?.result?.stdout ?? r?.text ?? ""), 0);
  else {
    const m = /^Exit code (\d+)\n?([\s\S]*)$/.exec(String(r.text ?? ""));
    out = m ? new ShellOutput(m[2]!, Number(m[1])) : new ShellOutput("", null, String(r.text ?? "Bash failed"));
  }
  if (out.exitCode === 1 && ANSWERS_WITH_1.test(cmd.trim())) out.note = "exit 1 is this command's answer (no match, files differ, a false test), not a failure";
  else if (o.throws && out.exitCode !== 0) throw new ShellError(out);
  return out;
}

function $(strings: TemplateStringsArray | string, ...values: unknown[]) {
  const cmd = typeof strings === "string"
    ? strings
    : strings.raw.map(s => s.replace(/\\(`|\$\{)/g, "$1")).reduce((acc, s, i) => acc + word(values[i - 1]) + s);
  const o: { throws: boolean; timeout?: number; cwd?: string; env?: Record<string, string> } = { throws: true };
  if (typeof strings === "string" && typeof values[0] === "number") o.timeout = values[0];
  let run: Promise<ShellOutput> | undefined;
  const exec = () => (run ??= runShell(cmd, o));
  // Like Bun.$, it starts on the next tick, so modifiers chained right after $ still apply.
  queueMicrotask(() => void exec().catch(() => {}));
  const p: any = {
    nothrow: () => ((o.throws = false), p),
    throws: (on: boolean) => ((o.throws = on), p),
    quiet: () => p,
    timeout: (ms: number) => ((o.timeout = ms), p),
    cwd: (d: string) => ((o.cwd = d), p),
    env: (v: Record<string, string>) => ((o.env = v), p),
    text: () => exec().then(r => r.stdout),
    lines: () => exec().then(r => r.lines()),
    json: () => exec().then(r => r.json()),
    then: (a?: any, b?: any) => exec().then(a, b),
    catch: (b?: any) => exec().catch(b),
    finally: (f?: any) => exec().finally(f),
  };
  return p;
}
$.escape = quote;
$.ShellError = ShellError;
g.$ = $;

// ---- files: Read, Edit and Write tool calls ----

const READ_PAGE = 2000;
async function readLines(path: string, offset: number, limit: number) {
  const r = await host("tool", { tool: "Read", args: { file_path: abs(path), offset, limit } });
  if (r?.isError) throw new Error(`file(${path}): ${r.text}`);
  const f = r?.result?.file;
  if (typeof f?.content !== "string") throw new Error(`file(${path}): not a text file`);
  return f as { content: string; numLines: number; startLine: number; totalLines: number };
}
/** The whole file, page by page through Read, so Read's hooks see every read. A page Read refuses as
 *  too large is asked for again with half the lines; a single line too large is an error. */
async function readAll(path: string) {
  const parts: string[] = [];
  let next = 1, total = Infinity, limit = READ_PAGE;
  while (next <= total) {
    let f;
    try {
      f = await readLines(path, next, limit);
    } catch (err) {
      if (limit === 1 || !/exceeds|too large|maximum/i.test(String(err))) throw err;
      limit = Math.ceil(limit / 2);
      continue;
    }
    parts.push(f.content);
    total = f.totalLines;
    if (!f.numLines) break;
    next = f.startLine + f.numLines;
  }
  return parts.join("\n");
}
g.file = (path: string) => ({
  name: abs(path),
  text: () => readAll(path),
  json: async () => JSON.parse(await readAll(path)),
  lines: async () => (await readAll(path)).split("\n"),
  exists: async () => {
    const out = await runShell(`test -e ${quote(abs(path))}`, { throws: false });
    if (out.exitCode === 0 || out.exitCode === 1) return out.exitCode === 0;
    throw new Error(`file(${path}).exists(): ${out.output}`);
  },
  slice: async (offset = 1, limit = READ_PAGE) => (await readLines(path, offset, limit)).content,
});
g.write = async (path: string, content: string) => {
  const r = await host("tool", { tool: "Write", args: { file_path: abs(path), content } });
  if (r?.isError) throw new Error(`write(${path}): ${r.text}`);
  return Buffer.byteLength(content);
};
const count = (s: string, sub: string) => (sub ? s.split(sub).length - 1 : 0);
g.edit = async (path: string, a: string | [string, string][], b?: string | { all?: boolean; soft?: boolean }, c?: { all?: boolean; soft?: boolean }) => {
  const edits: [string, string][] = Array.isArray(a) ? a : [[a, String(b)]];
  const opts = (Array.isArray(a) ? b : c) as { all?: boolean; soft?: boolean } | undefined ?? {};
  const fail = (error: string) => {
    if (opts.soft) return { ok: false, replacements: 0, error };
    throw new Error(error);
  };
  // Check every anchor, in order, against the text as the edits before it leave it.
  let text = await readAll(path), replacements = 0;
  for (const [old, next] of edits) {
    const n = count(text, old);
    if (n === 0) return fail(`edit(${path}): not found: ${old.slice(0, 200)}`);
    if (n > 1 && !opts.all) return fail(`edit(${path}): ${n} matches and an edit must match exactly once. Pass {all: true} to replace every match, or give more surrounding text so the match is unique: ${old.slice(0, 200)}`);
    text = opts.all ? text.split(old).join(next) : text.replace(old, () => next);
    replacements += opts.all ? n : 1;
  }
  for (const [old, next] of edits) {
    const r = await host("tool", { tool: "Edit", args: { file_path: abs(path), old_string: old, new_string: next, replace_all: opts.all === true } });
    if (r?.isError) return fail(`edit(${path}): ${r.text}`);
  }
  return { ok: true, replacements };
};

g.preview = (v: unknown, n = 200) => {
  const s = show(v);
  const size = v instanceof ShellOutput ? `[${s.length} chars of output] ` : "";
  return size + (s.length > n ? `${s.slice(0, n)}… [${s.length - n} more chars]` : s);
};

// ---- models, subagents, decisions (beyond Code Mode) ----

g.completion = (prompt: string, opts: object = {}) => host("complete", { prompt, ...opts });
g.agent = (prompt: string, opts: object = {}) => host("agent", { prompt, ...opts });
g.judge = (question: object, state: unknown) => host("judge", { question, state });
g.require = createRequire(join(process.cwd(), "noop.js")); // re-rooted at each script's cwd

const builtins = new Set(Object.keys(g));

// ---- making top-level declarations survive the cell ----
// ponytail: line-based rewrite of column-0 declarations, not a parser. Covers `const x =`, `let`,
// `var`, destructuring, `function`, `class` and static imports at the start of a line; indented
// declarations stay local to their cell. Upgrade path: a real parser (acorn) if models trip on it.

/** Marks a line that starts inside a string, template or comment, so the column-0 rewrites below
 *  leave it alone (a template holding `class X` or `const y =` at a line start is text, not code). */
const SHIELD = "\u0000";
// ponytail: no regex literals (a quote inside /…/ throws the scan off until the next quote).
function shield(code: string): string {
  let out = "", mode = "", depth = 0;
  const holes: number[] = []; // brace depth outside each open ${…} of a template
  const take = (i: number) => (out += code[i]) && code[i] === "\n" && mode ? (out += SHIELD) : "";
  for (let i = 0; i < code.length; i++) {
    const ch = code[i];
    if (ch === "\n" && mode === "//") mode = "";
    take(i);
    if (ch === "\n" || mode === "//") continue;
    if (mode === "/*") {
      if (ch === "*" && code[i + 1] === "/") (mode = "", take(++i));
    } else if (mode === "'" || mode === '"' || mode === "`") {
      if (ch === "\\") take(++i);
      else if (ch === mode) mode = "";
      else if (mode === "`" && ch === "$" && code[i + 1] === "{") (holes.push(depth), (depth = 0), (mode = ""), take(++i));
    } else if (ch === "'" || ch === '"' || ch === "`") mode = ch;
    else if (ch === "/" && (code[i + 1] === "/" || code[i + 1] === "*")) (mode = "/" + code[i + 1]), take(++i);
    else if (ch === "{") depth++;
    else if (ch === "}") depth === 0 && holes.length ? ((depth = holes.pop()!), (mode = "`")) : depth--;
  }
  return out;
}

function rewriteImports(code: string, cwd: string): string {
  const spec = (s: string) => JSON.stringify(s.startsWith(".") ? resolve(cwd, s) : s);
  return code
    .replace(/^import\s+\*\s+as\s+([\w$]+)\s+from\s+['"]([^'"]+)['"];?/gm, (_m, ns, s) => `globalThis.${ns} = await import(${spec(s)});`)
    .replace(/^import\s+\{([^}]*)\}\s+from\s+['"]([^'"]+)['"];?/gm, (_m, names: string, s) => {
      const parts = names.split(",").map(p => p.trim()).filter(Boolean).map(p => {
        const [from, to] = p.split(/\s+as\s+/);
        return `globalThis.${(to ?? from).trim()} = __m.${from.trim()};`;
      });
      return `{ const __m = await import(${spec(s)}); ${parts.join(" ")} }`;
    })
    .replace(/^import\s+([\w$]+)\s+from\s+['"]([^'"]+)['"];?/gm, (_m, name, s) => `globalThis.${name} = (await import(${spec(s)})).default;`)
    .replace(/^import\s+['"]([^'"]+)['"];?/gm, (_m, s) => `await import(${spec(s)});`);
}

/** Where the bracket opened at `i` closes, skipping strings; -1 when it doesn't. */
function closing(s: string, i: number): number {
  let depth = 0;
  for (let j = i; j < s.length; j++) {
    const ch = s[j];
    if (ch === "'" || ch === '"' || ch === "`") {
      for (j++; j < s.length && s[j] !== ch; j++) if (s[j] === "\\") j++;
    } else if (ch === "{" || ch === "[" || ch === "(") depth++;
    else if (ch === "}" || ch === "]" || ch === ")") if (--depth === 0) return j;
  }
  return -1;
}

const scanner = new Bun.Transpiler({ loader: "js" });

/** Rewrites top-level declarations so they land on globalThis; names lists what a destructuring binds. */
function persist(code: string): { body: string; names: string[] } {
  const names: string[] = [];
  // `const {a, b: c} = …` becomes `var {a, b: c} = …` (one scope for the whole script), and the
  // names it binds are copied to globalThis when the script ends. Bun's scanner reads the names off
  // the pattern as the exports of `export const <pattern> = 0`.
  const body = code.replace(/^(?:const|let|var)\s+(?=[{[])/gm, (m, at: number) => {
    const open = at + m.length, end = closing(code, open);
    if (end < 0) return m;
    try {
      names.push(...scanner.scan(`export const ${code.slice(open, end + 1)} = 0`).exports);
    } catch {
      return m;
    }
    return "var ";
  });
  return {
    names,
    body: body
      .replace(/^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/gm, "globalThis.$1 =")
      .replace(/^(async\s+)?function(\s*\*)?\s+([A-Za-z_$][\w$]*)/gm, (_m, a = "", star = "", name) => `globalThis.${name} = ${a}function${star} ${name}`)
      .replace(/^class\s+([A-Za-z_$][\w$]*)/gm, "globalThis.$1 = class $1"),
  };
}

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;

/** The line split after its last top-level `;` when code follows, so `const r = f(); 'got ' + r`
 *  ends in an expression of its own. */
function splitLast(line: string): string[] {
  let depth = 0, at = -1;
  for (let j = 0; j < line.length; j++) {
    const ch = line[j]!;
    if (ch === "'" || ch === '"' || ch === "`") {
      for (j++; j < line.length && line[j] !== ch; j++) if (line[j] === "\\") j++;
    } else if (ch === "/" && line[j + 1] === "/") break;
    else if ("([{".includes(ch)) depth++;
    else if (")]}".includes(ch)) depth--;
    else if (ch === ";" && depth === 0 && line.slice(j + 1).replace(/\/\/.*$/, "").trim()) at = j;
  }
  return at < 0 ? [line] : [line.slice(0, at + 1), line.slice(at + 1)];
}

/** Compile a cell; a trailing expression becomes its value, like a notebook. */
function compile(source: string, cwd: string): () => Promise<unknown> {
  const shielded = persist(rewriteImports(shield(source), cwd));
  const { names } = shielded, hasReturn = /^return\b/m.test(shielded.body);
  const body = shielded.body.replaceAll(SHIELD, "");
  const lines = body.trimEnd().split("\n");
  lines.push(...splitLast(lines.pop()!));
  // Bindings a destructuring made are copied out however the script ends (a var is hoisted, so
  // one never reached copies as undefined only if it is not already a global).
  const keep = names.length
    ? (b: string) => `try {\n${b}\n} finally {\n${names.map(n => `if (${n} !== undefined || !(${JSON.stringify(n)} in globalThis)) globalThis.${n} = ${n};`).join("\n")}\n}`
    : (b: string) => b;
  // ponytail: finds the last statement by trying `return (…)` over growing tails (last 1, 2, 3…
  // lines) and keeping the first that compiles. Upgrade path: a real parser (acorn).
  if (!hasReturn) {
    for (let k = 1; k <= lines.length; k++) {
      const first = lines[lines.length - k].trim();
      if (!first || /^(return|const|let|var|if|for|while|function|class|try|throw|\}|\/\/)/.test(first)) continue;
      const tail = lines.slice(-k).join("\n").trimEnd().replace(/;$/, "");
      try {
        return new AsyncFunction(keep([...lines.slice(0, -k), `return (${tail}\n);`].join("\n")));
      } catch {
        // not an expression from this line on
      }
    }
  }
  return new AsyncFunction(keep(body));
}

/** Keep the head and the tail, mark where the middle went. */
function cut(s: string, n = MAX_OUTPUT): string {
  if (s.length <= n) return s;
  return `${s.slice(0, n / 2)}\n… [${s.length - n} characters cut from the middle] …\n${s.slice(-n / 2)}`;
}

const thenable = (v: unknown): v is PromiseLike<unknown> => !!v && typeof (v as any).then === "function";
const plain = (v: unknown): v is Record<string, unknown> => !!v && Object.getPrototypeOf(v) === Object.prototype;

/** A returned object's promise values are awaited for it; a rejected one shows as its error. */
async function settle(v: unknown): Promise<unknown> {
  if (!plain(v)) return v;
  const entries = await Promise.all(Object.entries(v).map(async ([k, x]) =>
    [k, thenable(x) ? await Promise.resolve(x).catch((e: Error) => `Error: ${e?.message ?? e}`) : x] as const));
  return Object.fromEntries(entries);
}

/** Each key on its own, cut to PART: one long output doesn't push the others out. */
function render(v: unknown): string {
  if (!plain(v)) return cut(show(v), PART);
  return Object.entries(v).map(([k, x]) => {
    const s = cut(show(x), PART);
    return s.includes("\n") ? `${k}:\n${s}` : `${k}: ${s}`;
  }).join("\n");
}

/** Said once, in the first script a kernel runs, when an earlier kernel of the session ran scripts. */
const RESTARTED = "[repl] This kernel started fresh since your last script (the mod reloaded, the kernel was reset, or it crashed): variables from earlier scripts are gone.";
let ranHere = false;

function start(code: string, cwd: string): Cell {
  const c = new Cell(`${GEN}.k${++cellSeq}`, cwd);
  cells.set(c.id, c);
  if (marker && !ranHere) {
    if (existsSync(marker)) c.output.push(RESTARTED);
    try { writeFileSync(marker, ""); } catch {}
  }
  ranHere = true;
  // ponytail: the process cwd is shared, so a script's own fs calls with relative paths follow the
  // latest /run's cwd; the globals (file, $, edit, write) use the script's own. Upgrade path: none
  // short of one kernel per cwd (the "own" subagents option).
  process.chdir(cwd);
  // Scripts are not modules, so require() is given them, resolving from the working directory.
  g.require = createRequire(join(cwd, "noop.js"));
  current.run(c, async () => {
    try {
      const value = await settle(await compile(code, cwd)());
      const ev: Event = { status: "done", output: cut(c.output.join("\n"), PART) };
      if (value !== undefined) ev.value = cut(render(value));
      c.push(ev);
    } catch (err) {
      c.push({ status: "error", output: cut(c.output.join("\n"), PART), error: show(err) });
    } finally {
      // Calls still queued can't be answered and must not run now: drop them, so the cell's end is
      // the next event the mod sees. One already handed out is answered later; see /resume.
      end(c, "the script ended");
    }
  });
  return c;
}

// ---- HTTP over the Unix socket ----

const json = (v: unknown, status = 200) => Response.json(v, { status });
const missing = (what: string) => json({ status: "error", output: "", error: `no running script ${what}` }, 404);

async function nextOf(c: Cell): Promise<Response> {
  const ev = await c.next(WAIT_MS);
  if (ev.status === "done" || ev.status === "error") cells.delete(c.id);
  return json({ ...ev, cell: c.id });
}

if (existsSync(socket)) unlinkSync(socket);
Bun.serve({
  unix: socket,
  idleTimeout: 0, // a script may wait minutes on a subagent
  async fetch(req) {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/health") return json({ ok: true, pid: process.pid, running: cells.size });
    if (req.method === "GET" && url.pathname === "/vars") {
      const vars = Object.keys(g).filter(k => !builtins.has(k) && !k.startsWith("__")).map(k => ({ name: k, type: typeof g[k] }));
      return json({ vars });
    }
    if (req.method === "POST" && url.pathname === "/reset") {
      setTimeout(() => realExit(0), 10);
      return json({ ok: true });
    }
    if (req.method === "POST" && url.pathname === "/run") {
      const { code, cwd } = (await req.json()) as { code: string; cwd?: string };
      return nextOf(start(code, cwd ?? process.cwd()));
    }
    if (req.method === "POST" && (url.pathname === "/resume" || url.pathname === "/answer")) {
      const { callId, ok, value, error, cell } = (await req.json()) as { callId: string; ok: boolean; value?: unknown; error?: string; cell?: string };
      // An answer to a call of an earlier kernel: /answer drops it, /resume says its script is gone.
      if (!mine(String(callId))) {
        if (url.pathname === "/answer") return json({ ok: true, dropped: "from an earlier kernel" });
        return missing(String(cell));
      }
      const p = pending.get(callId);
      if (!p && cancelled.delete(callId)) {
        if (url.pathname === "/answer") return json({ ok: true });
        const c = cells.get(cell ?? "");
        return c ? nextOf(c) : missing(String(cell));
      }
      if (!p) return json({ status: "error", output: "", error: `no pending call ${callId}` }, 404);
      pending.delete(callId);
      ok ? p.resolve(value) : p.reject(new Error(error ?? "host call failed"));
      if (url.pathname === "/answer") return json({ ok: true });
      // Let the script run on the answer until it blocks again (a rejection may end it), so a call it
      // queued before that is not handed out to run after the script is gone.
      await new Promise(r => setImmediate(r));
      return nextOf(p.cell);
    }
    if (req.method === "POST" && url.pathname === "/next") {
      const { cell } = (await req.json().catch(() => ({}))) as { cell?: string };
      const c = cells.get(cell ?? "") ?? (cell === undefined && cells.size === 1 ? [...cells.values()][0] : undefined);
      return c ? nextOf(c) : missing(String(cell));
    }
    if (req.method === "POST" && url.pathname === "/cancel") {
      // ponytail: JavaScript can't be stopped from outside, so a cancelled script runs on until its
      // next host call, which rejects; a synchronous endless loop still needs /reset.
      const { cell, why } = (await req.json()) as { cell: string; why?: string };
      const c = cells.get(cell);
      if (c) {
        end(c, why ?? "interrupted");
        c.push({ status: "error", output: cut(c.output.join("\n"), PART), error: why ?? "interrupted" });
        cells.delete(c.id);
      }
      return json({ ok: true });
    }
    return json({ error: "not found" }, 404);
  },
});

const cleanup = () => {
  try {
    unlinkSync(socket);
  } catch {}
  realExit(0);
};
process.on("SIGTERM", cleanup);
process.on("SIGINT", cleanup);
// The mod kills us when its module unloads. If Claude Code itself dies we get re-parented; leave too.
const parent = process.ppid;
setInterval(() => process.ppid !== parent && cleanup(), 5_000).unref();
nativeConsole.log(JSON.stringify({ ready: true, socket, pid: process.pid }));
