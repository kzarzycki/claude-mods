// omc-eval kernel: a long-lived Bun process that keeps JavaScript state between cells.
//
// It serves HTTP on a Unix socket because a mod can't hold a child's stdin open across calls.
// A cell that needs the host (a Claude Code tool, a model, a subagent) does not reach Claude Code
// itself: it parks the call and hands it back to the mod as a `call` event; the mod runs it and
// answers with /resume. Every host call therefore goes through Claude Code's permissions and hooks.
//
//   POST /run     { code, timeoutMs? }            -> Event
//   POST /resume  { callId, ok, value?, error? }  -> Event   (answer a call, then the cell's next event)
//   POST /answer  { callId, ok, value?, error? }  -> { ok }  (answer a call without waiting)
//   POST /next                                    -> Event   (the running cell's next event)
//   POST /reset                                   -> exits; the mod starts a fresh kernel
//   GET  /health, GET /vars
//
// /answer + /next let a call be answered out of band: the mod answers a subagent's call from the
// subagent's own turn.complete hook while the eval hook waits on /next, so every wait the eval
// hook does is inside $.http.fetch, which its hook budget doesn't count.
//
// Event = { status: "call", callId, kind, payload }
//       | { status: "done", output, value? }
//       | { status: "error", output, error }

import { existsSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";

type Event =
  | { status: "call"; callId: string; kind: string; payload: unknown }
  | { status: "done"; output: string; value?: string }
  | { status: "error"; output: string; error: string };

const MAX_OUTPUT = 50_000;
const socket = process.argv[2];
if (!socket) throw new Error("usage: bun kernel.ts <socket path>");

// ---- one cell at a time: an event queue the HTTP handlers pull from ----

class Cell {
  events: Event[] = [];
  waiter: ((e: Event) => void) | undefined;
  output: string[] = [];
  push(e: Event) {
    if (this.waiter) {
      const w = this.waiter;
      this.waiter = undefined;
      w(e);
    } else this.events.push(e);
  }
  next(): Promise<Event> {
    const e = this.events.shift();
    return e ? Promise.resolve(e) : new Promise(r => (this.waiter = r));
  }
}

let cell: Cell | undefined;
const pending = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
let callSeq = 0;

function host(kind: string, payload: unknown): Promise<any> {
  const current = cell;
  if (!current) return Promise.reject(new Error("host calls are only available while a cell runs"));
  const callId = `c${++callSeq}`;
  return new Promise((res, rej) => {
    pending.set(callId, { resolve: res, reject: rej });
    current.push({ status: "call", callId, kind, payload });
  });
}

function show(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === undefined) return "undefined";
  try {
    return JSON.stringify(v, null, 2) ?? String(v);
  } catch {
    return String(v);
  }
}

function write(line: string) {
  cell?.output.push(line);
}

// ---- the prelude: what a cell sees besides Bun, fetch, fs, process ----

const g = globalThis as any;
const nativeConsole = { log: console.log, error: console.error, warn: console.warn, info: console.info };
for (const k of ["log", "info", "warn", "error"] as const) {
  console[k] = (...a: unknown[]) => write(a.map(show).join(" "));
}

/** tool.Read({ file_path }) resolves to the tool's text; an errored tool throws. */
g.tool = new Proxy(
  {},
  {
    get: (_t, name: string) => {
      if (name === "call") return (tool: string, args: object = {}, opts: { raw?: boolean } = {}) => callTool(tool, args, opts.raw);
      if (name === "then") return undefined; // so `await tool` doesn't hang
      return (args: object = {}) => callTool(name, args, false);
    },
  },
);
async function callTool(name: string, args: object, raw?: boolean) {
  const r = await host("tool", { tool: name, args });
  if (raw) return r;
  if (r?.isError) throw new Error(`${name} failed: ${r.text ?? "no detail"}`);
  return r?.text ?? r?.result;
}
g.tools = () => host("tools", {});
g.completion = (prompt: string, opts: object = {}) => host("complete", { prompt, ...opts });
g.agent = (prompt: string, opts: object = {}) => host("agent", { prompt, ...opts });
g.judge = (question: object, state: unknown) => host("judge", { question, state });
g.display = (v: unknown) => write(show(v));
g.sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

const builtins = new Set(Object.keys(g));

// ---- making top-level declarations survive the cell ----
// ponytail: line-based rewrite of column-0 declarations, not a parser. Covers `const x =`, `let`,
// `var`, `function`, `class` and static imports at the start of a line; destructuring and indented
// declarations stay local to their cell. Upgrade path: rewrite with Bun.Transpiler's AST or a real
// parser (acorn) if models trip on it.

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

function persist(code: string): string {
  return code
    .replace(/^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/gm, "globalThis.$1 =")
    .replace(/^(async\s+)?function(\s*\*)?\s+([A-Za-z_$][\w$]*)/gm, (_m, a = "", star = "", name) => `globalThis.${name} = ${a}function${star} ${name}`)
    .replace(/^class\s+([A-Za-z_$][\w$]*)/gm, "globalThis.$1 = class $1");
}

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;

/** Compile a cell; a trailing expression becomes its value, like a notebook. */
function compile(source: string, cwd: string): () => Promise<unknown> {
  const body = persist(rewriteImports(source, cwd));
  const lines = body.trimEnd().split("\n");
  const last = lines[lines.length - 1]?.trim() ?? "";
  const canReturn = last && !/^(return|const|let|var|if|for|while|function|class|try|throw|\}|\/\/)/.test(last) && !/\breturn\b/.test(body);
  if (canReturn) {
    try {
      return new AsyncFunction([...lines.slice(0, -1), `return (${last.replace(/;$/, "")});`].join("\n"));
    } catch {
      // not an expression after all
    }
  }
  return new AsyncFunction(body);
}

function cut(s: string): string {
  return s.length > MAX_OUTPUT ? `${s.slice(0, MAX_OUTPUT)}\n… [${s.length - MAX_OUTPUT} more characters cut]` : s;
}

function start(code: string, cwd: string): Cell {
  const c = new Cell();
  cell = c;
  (async () => {
    try {
      const value = await compile(code, cwd)();
      const ev: Event = { status: "done", output: cut(c.output.join("\n")) };
      if (value !== undefined) ev.value = cut(show(value));
      c.push(ev);
    } catch (err) {
      const e = err as Error;
      c.push({ status: "error", output: cut(c.output.join("\n")), error: e?.stack ?? String(err) });
    } finally {
      if (cell === c) cell = undefined;
      for (const [id, p] of pending) {
        p.reject(new Error("cell ended"));
        pending.delete(id);
      }
    }
  })();
  return c;
}

// ---- HTTP over the Unix socket ----

let running: Cell | undefined;
const json = (v: unknown, status = 200) => Response.json(v, { status });

async function nextOf(c: Cell): Promise<Response> {
  const ev = await c.next();
  if (ev.status !== "call") running = undefined;
  return json(ev);
}

if (existsSync(socket)) unlinkSync(socket);
Bun.serve({
  unix: socket,
  idleTimeout: 0, // a cell may wait minutes on a subagent
  async fetch(req) {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/health") return json({ ok: true, pid: process.pid, busy: !!running });
    if (req.method === "GET" && url.pathname === "/vars") {
      const vars = Object.keys(g).filter(k => !builtins.has(k) && !k.startsWith("__")).map(k => ({ name: k, type: typeof g[k] }));
      return json({ vars });
    }
    if (req.method === "POST" && url.pathname === "/reset") {
      setTimeout(() => process.exit(0), 10);
      return json({ ok: true });
    }
    if (req.method === "POST" && url.pathname === "/run") {
      if (running) return json({ status: "error", output: "", error: "another cell is still running" }, 409);
      const { code, cwd } = (await req.json()) as { code: string; cwd?: string };
      running = start(code, cwd ?? process.cwd());
      return nextOf(running);
    }
    if (req.method === "POST" && (url.pathname === "/resume" || url.pathname === "/answer")) {
      const { callId, ok, value, error } = (await req.json()) as { callId: string; ok: boolean; value?: unknown; error?: string };
      const p = pending.get(callId);
      if (!p || !running) return json({ status: "error", output: "", error: `no pending call ${callId}` }, 404);
      pending.delete(callId);
      ok ? p.resolve(value) : p.reject(new Error(error ?? "host call failed"));
      return url.pathname === "/answer" ? json({ ok: true }) : nextOf(running);
    }
    if (req.method === "POST" && url.pathname === "/next") {
      if (!running) return json({ status: "error", output: "", error: "no cell is running" }, 404);
      return nextOf(running);
    }
    return json({ error: "not found" }, 404);
  },
});

const cleanup = () => {
  try {
    unlinkSync(socket);
  } catch {}
  process.exit(0);
};
process.on("SIGTERM", cleanup);
process.on("SIGINT", cleanup);
// The mod kills us when its module unloads. If Claude Code itself dies we get re-parented; leave too.
const parent = process.ppid;
setInterval(() => process.ppid !== parent && cleanup(), 5_000).unref();
nativeConsole.log(JSON.stringify({ ready: true, socket, pid: process.pid }));
