import type { EngineInterface, Register } from "claude-code";

// code-mode: Claude Code's Code Mode as a mod. One `repl` tool runs JavaScript in a long-lived Bun
// kernel (../kernel/kernel.ts) that keeps state between calls, with Code Mode's globals ($, file,
// edit, write, preview, tools, searchTools, ...). A script's host calls come back here as `call`
// events; this module runs them through $ (Bash, Read, Edit and Write for the shell and file
// globals), so each one runs Claude Code's tool with its hooks (PreToolUse, every other plugin's
// tool.call hooks). Deny rules don't apply: they bind only the model's own calls.
//
// The guide below is Code Mode's own prompt text where it fits, delivered as the tool's description
// by a tool.describe hook, or as the system prompt by a launcher that passes guide.ts's output to
// --append-system-prompt, a CLI flag no mod can skip. The mod can't put it there itself: an
// organization's sec-default mod skips a person's prompt.compose, prompt.section and
// prompt.context hooks, but not tool.describe, and a description set there reaches the model whole
// (the 4,096-character cap is on $.tool.register's description). Two modes:
// - preferred: the other tools stay; the section says repl is the better way for most work.
// - exclusive: the session denies the built-ins (`--disallowedTools Bash Read ...`) and repl is
//   the one way; scripts still reach those tools, because a deny rule stops only the model.

const TOOL = "repl";
const TOOL_ID = "mcp__code-mode__repl";
const DESCRIPTION = "Run JavaScript in a persistent REPL: shell commands, file reads, writes and edits, code search and tool calls, as one script. Persistent state, Code Mode's globals ($, file, edit, write, tools).";

/** The built-ins whose absence means the session runs repl as its one way to work. */
const EXCLUSIVE_WHEN_MISSING = ["Bash", "Read", "Edit"];

/** What the guide says about subagents' REPL, by the subagents option. */
const SUBAGENTS = {
  shared: "Subagents share this context: a subagent you start (with `agent()` or the Agent tool) runs its scripts here beside yours, so it sees your variables and you see the ones it makes. Hand data over through a variable instead of pasting it into a prompt, and give what you make names that won't clash (`const auditFindings`, not `const out`).",
  own: "Each subagent has a REPL context of its own: it doesn't see your variables, so put what it needs in its prompt.",
};

const OPENER = {
  exclusive: "Work through `repl`: this session has no shell, file or search tools of its own. Everything you do — shell commands, file reads and edits, code search, web fetches, MCP calls — happens as JavaScript inside a `repl` call, through the globals below.",
  preferred: "Prefer `repl` for the work you do in this session: shell commands, file reads and edits, code search, and chains of tool calls happen as JavaScript inside a `repl` call, through the globals below. The other tools in your list stay available and are also callable from a script, by name. Call one directly when it is a single call whose whole output you need, or when a script would only wrap it.",
};

const EXAMPLE = `One script can look in several places at once and then act on what it found, for example:
\`\`\`js
const [defs, uses] = await Promise.all([
  $\`rg -l "function retryPolicy" src\`.text(),
  $\`rg -lF "retryPolicy(" src test\`.text(),
]);
const target = defs.trim().split('\\n')[0];                 // the file that defines it
if (!target) throw new Error('nothing defines retryPolicy: not editing');
await edit(target, 'maxAttempts: 3', 'maxAttempts: 5');
({edited: target, callers: uses.trim().split('\\n').filter(f => f !== target), test: $\`npm test -- retryPolicy\`.nothrow()})
\`\`\``;

const DECLARATIONS = `\`\`\`ts
// The globals of a repl script, as TypeScript declarations.
/** Runs a command as one call of Claude Code's Bash tool, so it shows in the transcript and the Bash tool's hooks run on it; deny rules, which bind only your own calls, don't apply. The template text goes to the shell as written, except that \\\` and \\\${ lose their backslash, so a backtick or \${ the shell should see literally goes in as a \${} value. $ single-quotes each string \${} value itself as one argument (an array: one per item; \${{raw: s}} splices s unquoted), so write \${x} bare: inside quote marks of your own, the quotes $ added no longer protect the value. $(cmd, ms) runs a command given as a plain string, with an optional timeout in ms. A non-zero exit throws a ShellError; .nothrow() hands back the ShellOutput whatever the exit code. An exit 1 from a line whose last command is grep (also rg, egrep, fgrep), find, diff, test or \`[\`, git diff or git grep is read as that command's outcome (no match, files differ, a false test) and does not throw: exitCode is 1 and note gives the reading. Output the Bash tool cuts or saves to a file is cut the same way here. */
declare function $(strings: TemplateStringsArray, ...values: unknown[]): ShellPromise;
declare function $(cmd: string, timeoutMs?: number): ShellPromise;
declare namespace $ {
  function escape(s: string): string;
  const ShellError: new (out: ShellOutput) => ShellError;
}
interface ShellPromise extends Promise<ShellOutput> {
  nothrow(): ShellPromise;
  throws(on: boolean): ShellPromise;
  quiet(): ShellPromise;
  timeout(ms: number): ShellPromise;
  cwd(dir: string): ShellPromise;
  env(vars: Record<string, string>): ShellPromise;
  text(): Promise<string>;
  lines(): Promise<string[]>;
  json(): Promise<unknown>;
}
interface ShellOutput {
  /** the command's stderr is merged into stdout, so 2>&1 adds nothing */
  stdout: string;
  stderr: string;
  /** null when the call failed outside the command (a denial): error says why */
  exitCode: number | null;
  text(): string;
  lines(): string[];
  json(): unknown;
  /** the text the result shows: stdout, then [error] and [exit N] when there are any */
  output: string;
  error?: string;
  note?: string;
}
interface ShellError extends Error { stdout: string; stderr: string; exitCode: number | null }
/** An exact-string edit through the Edit tool (next inserted literally); throws on zero or several matches, {all} replaces every match, {soft} resolves {ok: false, error} instead. The batch form checks every anchor, in order, before it writes, so an anchor not found, or found more than once without {all}, leaves the file untouched; a failure after that (a permission denial, say) leaves the edits before it applied. */
declare function edit(path: string, old: string, next: string, opts?: { all?: boolean; soft?: boolean }): Promise<{ ok: boolean; replacements: number; error?: string }>;
declare function edit(path: string, edits: [old: string, next: string][], opts?: { all?: boolean; soft?: boolean }): Promise<{ ok: boolean; replacements: number; error?: string }>;
/** Writes a whole file through the Write tool (directories created); resolves the byte count. */
declare function write(path: string, content: string): Promise<number>;
/** One file, read through the Read tool when a method is called; a relative path is from the working directory. */
declare function file(path: string): {
  name: string;
  text(): Promise<string>;
  json(): Promise<unknown>;
  lines(): Promise<string[]>;
  /** whether the path exists, asked as a \`test -e\` Bash tool call */
  exists(): Promise<boolean>;
  /** lines from the 1-based line offset, at most limit (2000 by default) */
  slice(offset?: number, limit?: number): Promise<string>;
};
/** Resolves after ms. */
declare function sleep(ms: number): Promise<void>;
/** The first n chars (200 by default) of the value, with a marker when it cuts; for a $ result, its size first. */
declare function preview(value: unknown, n?: number): string;
/** The output channel: each call is a line delivered with the result. */
declare function log(...args: unknown[]): void;
/** globalThis, so self.log is log. */
declare const self: typeof globalThis;
/** Not delivered with the result; tail(n) reads the last n lines back. */
declare var console: { log(...a: unknown[]): void; info(...a: unknown[]): void; debug(...a: unknown[]): void; warn(...a: unknown[]): void; error(...a: unknown[]): void; tail(n?: number): string; buffer(): string; dropped(): number };
/** Every tool in this session, by name: tools.mcp__linear__list_issues({...}), tools.Skill({skill}). tools.list() gives the names; a tool the session doesn't have (some builds have no Grep or Glob: search with $\`rg\`) throws. Built-in tools resolve {error: string} on failure; MCP tool calls THROW on failure: catch only where you can genuinely proceed without the result, and never treat a caught failure as success. */
declare const tools: Record<string, (input?: object) => Promise<any>> & { list(): Promise<string[]> };
/** The tools a script can call, by words from their name or description. input is not known here: read the tool's description, or call it and read the error. Resolves {error} for an empty query. */
declare function searchTools(query: string, max?: number): Promise<{ name: string; about: string; input: string }[] | { error: string }>;
/** One tool's description; {error} for a name no tool has. */
declare function describeTool(name: string): Promise<{ name: string; description: string } | { error: string }>;
/** A subagent: resolves its hand-back report (with a JSON Schema schema, the parsed JSON). Several run in parallel under Promise.all. */
declare function agent(prompt: string, opts?: { description?: string; subagentType?: string; model?: string; schema?: object }): Promise<unknown>;
/** One model completion; resolves its text. */
declare function completion(prompt: string, opts?: { model?: string; system?: string; maxTokens?: number }): Promise<string>;
/** Asks the decision model one typed question (needs the decision-model mod): {type: "noul" | "choice" | "score", instructions, criteria?}. */
declare function judge(question: object, state: unknown): Promise<unknown>;
\`\`\``;

/** The Code Mode guide: Code Mode's own prompt text, adapted to this kernel. ../guide.ts prints it for a launcher's system prompt. */
export function section(mode: "exclusive" | "preferred", subagents: "shared" | "own" = "shared"): string {
  return `# Code Mode
${OPENER[mode]}
The REPL is one persistent JavaScript context: variables and functions you define in one call are there in the next, so keep results in variables (\`const out = await $\`…\`.text()\`) instead of re-reading a file or re-running a command whose output you already hold. Top-level \`const\`, \`let\`, \`var\` (destructuring too), \`function\` and \`class\` declarations at the start of a line persist; indented ones stay in their script. Those variables last between calls, through compaction and /clear, but not across a restart or a resume of Claude Code, or \`reset: true\`; a result that starts with a \`[repl]\` line says the kernel started fresh and earlier variables are gone. ${SUBAGENTS[subagents]} Top-level \`await\` works. \`import\`, \`require\`, Bun and \`node:*\` modules work, but they go around Claude Code: the person can't see that work and no permission check covers it, so reach the machine through the globals below. The REPL language is always JavaScript, whatever the codebase is written in — run the codebase's own tools (pytest, cargo, go test, …) with \`$\`.
What a \`repl\` call costs: each call is a full model round-trip — the whole conversation is re-read before your script runs, and you wait for the reply — while the work inside a script (shell commands, file reads, searches, tool calls) is comparatively free, and runs concurrently when you fan it out with \`Promise.all\`. So the expensive thing is coming back to decide, not doing more in one go: gather what a decision could plausibly need in the script you are already writing, and come back for another call when the next step depends on what this one shows you.
A script's output is its last expression's value plus anything it \`self.log(...)\`s along the way. What it returns is added to your context and stays there; the value itself stays in the REPL whether you return it or not. So return what you want to read now, and keep the rest in variables to slice or search later. Each part of what a script returns (each key of a returned object, what it logged) is shown cut to about 20,000 characters, head and tail kept, with a marker where the middle went. Promise values inside a returned object are awaited for you (\`({status: $\`git status\`, branches: $\`git branch\`})\` needs no awaits); a promise used inline — concatenated, interpolated, passed to another call — needs \`await\`. \`console.*\` goes to a bounded in-memory ring rather than into your context; \`console.tail(n)\` reads it back.
To keep a long output out of your context, return \`preview(out)\` or \`preview(out, 2000)\` instead of the output itself: it gives the first characters, and when \`out\` is an awaited \`$\` result (not its \`.text()\` string), it starts with the output's size.
A call's result is the log lines, then \`=> \` and the returned value (or \`Error: \` and the error). A call waits for its script to end, however long it runs.
${EXAMPLE}
## Declarations
${DECLARATIONS}`;
}

type Event = (
  | { status: "call"; callId: string; kind: string; payload: any }
  | { status: "wait" }
  | { status: "done"; output: string; value?: string }
  | { status: "error"; output: string; error: string }
) & { cell?: string };

/** The main session's kernel socket; set once the session starts. */
let sock = "";
/** With the "own" subagents option: each subagent's kernel socket, started at its first repl call. */
// ponytail: a subagent's kernel lives as long as the session (it may be resumed). Upgrade path: stop it after the agent's last turn.
const agentKernels = new Map<string, string>();
/** Session id and options, kept from session.start for kernels started later. */
let session = { id: "", bun: "bun", cwd: "" };
/** Subagents a running script waits on: agentId → the kernel's callId, the schema its answer must match and the kernel it waits in. */
const agentCalls = new Map<string, { callId: string; schema?: unknown; at: string }>();

/** Every subagent a script started; their completion notices belong to the script, not the parent. */
// ponytail: grows for the session's life (a few ids per agent() call).
const scriptAgents = new Set<string>();

/** The agent ids a delivered notice is about: task-notification tags or a hand-back's sender. */
function noticeAgents(text: string): string[] {
  return [...text.matchAll(/<task-id>([\w-]+)<\/task-id>|from="([\w-]+)"/g)].map(m => (m[1] ?? m[2])!);
}

/** The subagent's hand-back is a report to a program, so ask for the answer alone. */
function agentPrompt(prompt: string, schema: unknown): string {
  return schema === undefined
    ? `${prompt}\n\nYour hand-back report is returned verbatim to a program as your answer: make it only the answer, with no preamble, summary or sign-off.`
    : `${prompt}\n\nYour hand-back report is parsed by a program: make it only a JSON value matching this JSON Schema, with no prose and no code fences.\n${JSON.stringify(schema)}`;
}

/** The answer a script's agent() resolves to; with a schema, the parsed JSON. */
function agentAnswer(text: string, schema: unknown): { ok: true; value: unknown } | { ok: false; error: string } {
  if (schema === undefined) return { ok: true, value: text.trim() };
  // ponytail: parses only, no schema validation. Upgrade path: validate and send the subagent the errors to fix.
  try {
    return { ok: true, value: JSON.parse(text.trim().replace(/^```(?:json)?\s*|\s*```$/g, "")) };
  } catch {
    return { ok: false, error: `agent: the answer is not JSON: ${text.slice(0, 200)}` };
  }
}

/** The kernel refused a /resume or /next: it and this mod disagree about the running script. */
class KernelLost extends Error {}

async function post($: EngineInterface, path: string, body: unknown = {}, at = sock): Promise<any> {
  const res = await $.http.fetch(`http://localhost${path}`, { method: "POST", socketPath: at, body: JSON.stringify(body), headers: { "Content-Type": "application/json" } });
  const ev = JSON.parse(res.text);
  // A refusal means the kernel no longer knows the script (it restarted, say): it can't be driven.
  if (!res.ok) throw new KernelLost(`${path}: ${ev.error ?? res.status}`);
  return ev;
}

/** Start a kernel on a fresh socket and keep it running; key names its marker file (main or an agent id). */
function startKernel($: EngineInterface, key: string): string {
  // Unix socket paths are capped near 104 bytes, so /tmp rather than the plugin's folder.
  const at = `/tmp/code-mode-${session.id.slice(0, 8)}-${Math.random().toString(36).slice(2, 8)}.sock`;
  // The marker outlives a mod reload, so a kernel that replaces an earlier one can say variables are gone.
  const marker = `/tmp/code-mode-${session.id}-${key}.ran`;
  void supervise($, [session.bun, `${$.plugin.root}/kernel/kernel.ts`, at, "20000", marker], session.cwd);
  return at;
}

/** The kernel a repl call runs in: the session's, or with "own" subagents, the calling subagent's. */
function kernelFor($: EngineInterface, agentId: string | undefined, subagents: string): string {
  if (subagents !== "own" || !agentId) return sock;
  let at = agentKernels.get(agentId);
  if (!at) agentKernels.set(agentId, (at = startKernel($, agentId)));
  return at;
}

/** Wait (up to ~5 s) for the kernel to answer /health. */
async function ready($: EngineInterface, at = sock): Promise<boolean> {
  for (let i = 0; i < 50; i++) {
    try {
      const res = await $.http.fetch("http://localhost/health", { socketPath: at });
      if (res.ok) return true;
    } catch {}
    await $.clock.sleep(100);
  }
  return false;
}

/** Keep one kernel alive for the session: a child that exits (reset, crash) is started again. */
async function supervise($: EngineInterface, argv: string[], cwd: string) {
  // ponytail: fixed restart cap, no backoff. Upgrade path: back off on quick consecutive exits.
  for (let starts = 0; starts < 50; starts++) {
    try {
      for await (const chunk of $.process.spawn({ argv, cwd })) $.ui.log(`code-mode kernel: ${chunk.text.trimEnd()}`, { to: "debug" });
    } catch (err) {
      $.ui.log(`code-mode kernel failed to start: ${String(err)}`, { to: "debug" });
      await $.clock.sleep(1000);
    }
  }
}

/** Run one host call a script made. Throws to make the script's await reject. */
async function hostCall($: EngineInterface, kind: string, p: any): Promise<unknown> {
  if (kind === "tool") {
    if (p.tool === TOOL_ID) throw new Error("a script can't call repl itself");
    const r = await $.tool.call({ tool: String(p.tool), ...(p.args ?? {}) });
    if (r.deny !== undefined) return { isError: true, text: `denied: ${r.deny}` };
    return { text: r.text ?? (typeof r.result === "string" ? r.result : JSON.stringify(r.result)), result: r.result, isError: r.isError === true };
  }
  if (kind === "tools") return await $.tool.list();
  if (kind === "complete") {
    const r = await $.model.complete({ model: String(p.model ?? "haiku"), prompt: String(p.prompt), system: p.system, maxTokens: p.maxTokens, effort: p.effort });
    if (!r.isAnswered) throw new Error(`completion failed: ${r.reason}`);
    return r.text;
  }
  if (kind === "judge") {
    // Optional: decision-model adds $.decision when it is loaded; code-mode works without it.
    type Ask = { decision: { ask: (r: object) => Promise<{ answers: Record<string, unknown> }> } };
    let r: { answers: Record<string, unknown> };
    try {
      r = await ($ as unknown as Ask).decision.ask({ purpose: "repl", state: p.state, questions: { q: p.question } });
    } catch (err) {
      if (err instanceof TypeError && /decision/.test(err.message)) throw new Error("judge() needs the decision-model mod");
      throw err;
    }
    return r.answers.q;
  }
  throw new Error(`unknown host call ${kind}`);
}

/** Run a script to its end in the kernel at `at`, answering its host calls. */
async function runScript($: EngineInterface, code: string, maxCalls: number, signal?: AbortSignal, at = sock): Promise<Event> {
  if (!(await ready($, at))) return { status: "error", output: "", error: "the kernel is not running (is bun installed? see /repl)" };
  // An interrupt cancels this script alone: other scripts in the kernel, and its variables, stay.
  const run = { cell: "" };
  const interrupted = () => void (run.cell && post($, "/cancel", { cell: run.cell, why: "interrupted" }, at).catch(() => {}));
  signal?.addEventListener("abort", interrupted, { once: true });
  try {
    return await drive($, code, maxCalls, run, at, signal);
  } catch (err) {
    if (signal?.aborted) return { status: "error", output: "", error: "interrupted" };
    if (err instanceof KernelLost) return { status: "error", output: "", error: `the kernel lost track of the script (${err.message}); it most likely restarted, so earlier variables are gone` };
    throw err;
  } finally {
    signal?.removeEventListener("abort", interrupted);
  }
}

async function drive($: EngineInterface, code: string, maxCalls: number, run: { cell: string }, at: string, signal?: AbortSignal): Promise<Event> {
  const interrupted: Event = { status: "error", output: "", error: "interrupted" };
  if (signal?.aborted) return interrupted;
  let ev: Event = await post($, "/run", { code, cwd: await $.session.cwd() }, at);
  const cell = (run.cell = ev.cell ?? "");
  let calls = 0;
  while (ev.status === "call" || ev.status === "wait") {
    // An interrupt that came before the cell id was known (during /run) had nothing to cancel then.
    if (signal?.aborted) {
      await post($, "/cancel", { cell, why: "interrupted" }, at).catch(() => {});
      return interrupted;
    }
    if (ev.status === "wait") {
      // The kernel answers "wait" every ~20 s so no request outlives the host's fetch limit.
      ev = await post($, "/next", { cell }, at);
      continue;
    }
    if (++calls > maxCalls) {
      const error = `the script made more than ${maxCalls} host calls and was stopped`;
      await post($, "/cancel", { cell, why: error }, at).catch(() => {});
      return { status: "error", output: "", error };
    }
    const { callId, kind, payload } = ev;
    if (kind === "agent") {
      // Answered later by the subagent's own hand-back (below); meanwhile take the next event. Only a
      // failed spawn answers the call here: once the agent runs, its answer may already be in.
      let agentId: string;
      try {
        const spawned = await $.agent.spawn({ prompt: agentPrompt(String(payload.prompt), payload.schema), description: String(payload.description ?? "repl script subagent"), subagentType: payload.subagentType, model: payload.model });
        if (spawned.deny !== undefined || !spawned.agentId) throw new Error(spawned.deny ?? "no agent id");
        agentId = spawned.agentId;
      } catch (err) {
        ev = await post($, "/resume", { callId, ok: false, error: `agent: ${String(err)}`, cell }, at);
        continue;
      }
      agentCalls.set(agentId, { callId, schema: payload.schema, at });
      scriptAgents.add(agentId);
      ev = await post($, "/next", { cell }, at);
      continue;
    }
    try {
      ev = await post($, "/resume", { callId, ok: true, value: await hostCall($, kind, payload), cell }, at);
    } catch (err) {
      if (err instanceof KernelLost) throw err;
      ev = await post($, "/resume", { callId, ok: false, error: err instanceof Error ? err.message : String(err), cell }, at);
    }
  }
  // A script that ended while the interrupt was on its way still reports the interrupt, not its value.
  return signal?.aborted ? interrupted : ev;
}

function render(ev: Event): string {
  if (ev.status === "error") return [ev.output, `Error: ${ev.error}`].filter(Boolean).join("\n");
  if (ev.status === "done") return [ev.output, ev.value !== undefined ? `=> ${ev.value}` : ""].filter(Boolean).join("\n") || "(no output)";
  return "(script still running)";
}

export const register: Register = (on, options) => {
  const bun = String(options.bun || "bun");
  const maxCalls = Number(options.maxCalls ?? 200);
  const mode = String(options.mode || "auto");
  const subagents = options.subagents === "own" ? "own" : "shared";

  on("session.start", async ($, e, next) => {
    session = { id: await $.session.id(), bun, cwd: e.cwd };
    sock = startKernel($, "main");
    await $.tool.register({
      name: TOOL,
      description: DESCRIPTION,
      isDeferred: false, // behind ToolSearch the model reaches for Bash before it finds repl
      inputSchema: {
        type: "object",
        properties: {
          code: { type: "string", description: "JavaScript to run as one script" },
          title: { type: "string", description: "Short label for the script, shown to the user" },
          reset: { type: "boolean", description: "Restart the kernel with empty state before running" },
        },
        required: ["code"],
      },
    });
    await $.command.register({ name: "repl", description: "code-mode REPL: `/repl vars`, `/repl reset`, or `/repl <code>` to run a script yourself", argumentHint: "vars | reset | <code>" });
    return next(e);
  });

  // The Code Mode guide as the tool's description. Exclusive wording when the model can call none
  // of Bash, Read and Edit (the session denied them), preferred otherwise.
  on("tool.describe", { tool: TOOL_ID }, async ($, e, next) => {
    const r = await next(e);
    // A launcher that put the guide in the system prompt (bun guide.ts) sets this, so it isn't sent twice.
    if ((await $.env.get("CODE_MODE_GUIDE")) === "system") return { ...r, description: `${DESCRIPTION} How to use it: the Code Mode section of your system prompt.` };
    const offered = new Set((await $.tool.list()).map(t => t.name));
    const exclusive = mode === "exclusive" || (mode === "auto" && EXCLUSIVE_WHEN_MISSING.every(t => !offered.has(t)));
    return { ...r, description: section(exclusive ? "exclusive" : "preferred", subagents) };
  });

  on("tool.call", { tool: TOOL_ID }, async ($, e, next) => {
    const input = e as unknown as { code?: unknown; reset?: unknown };
    const at = kernelFor($, e.agentId, subagents);
    if (input.reset === true) {
      await post($, "/reset", {}, at).catch(() => {});
      await $.clock.sleep(200);
    }
    if (typeof input.code !== "string" || !input.code.trim()) return input.reset === true ? { result: "kernel reset" } : { isError: true, result: "code is required" };
    const ev = await runScript($, input.code, maxCalls, next.signal, at);
    return ev.status === "error" ? { isError: true, result: render(ev) } : { result: render(ev) };
  });

  // A subagent hands its report back with the SubagentHandback tool; that report answers the
  // script's agent() call.
  // ponytail: matched by hand because SubagentHandback is missing from this build's typed tool list.
  on("tool.call", async ($, e, next) => {
    const call = (e.tool as string) === "SubagentHandback" && e.agentId ? agentCalls.get(e.agentId) : undefined;
    if (e.agentId && call) {
      agentCalls.delete(e.agentId);
      const message = (e as unknown as { message?: unknown }).message;
      const answer = agentAnswer(typeof message === "string" ? message : JSON.stringify(message), call.schema);
      await post($, "/answer", { callId: call.callId, ...answer }, call.at).catch(() => {});
      // The script is the recipient: answering the hand-back here keeps it out of the parent's
      // conversation, where each report would otherwise start a turn of its own.
      return { result: "Delivered to the repl script that started you." };
    }
    return next(e);
  });

  // A script's subagent runs in the background, so its end is also announced to the parent session,
  // which would spend a turn on each one. The script already has the answer: drop those notices.
  on("prompt.submit", async ($, e, next) => {
    const ids = e.origin.kind === "task-notification" || e.origin.kind === "peer" || e.origin.kind === "peer-send-message" ? noticeAgents(e.text) : [];
    if (ids.length && ids.every(id => scriptAgents.has(id))) return { drop: "code-mode: a script's subagent finished; the script has its answer" };
    return next(e);
  });

  // A subagent that ended without handing back: its final text (if any) answers the call.
  on("turn.complete", async ($, e, next) => {
    const call = e.agentId ? agentCalls.get(e.agentId) : undefined;
    if (e.agentId && call) {
      agentCalls.delete(e.agentId);
      const answer = e.reason === "answer" ? agentAnswer(e.answer, call.schema) : { ok: false, error: `subagent ended: ${e.reason}` };
      await post($, "/answer", { callId: call.callId, ...answer }, call.at).catch(() => {});
    }
    return next(e);
  });

  on("command.run", { command: "repl" }, async ($, e, next) => {
    const arg = e.args.trim();
    if (!(await ready($))) return { text: `kernel not running at ${sock} (runtime: ${bun})`, exitCode: 1 };
    if (arg === "" || arg === "vars") {
      const res = await $.http.fetch("http://localhost/vars", { socketPath: sock });
      const vars = (JSON.parse(res.text).vars as { name: string; type: string }[]).map(v => `${v.name}: ${v.type}`);
      return { text: vars.length ? vars.join("\n") : "no variables yet" };
    }
    if (arg === "reset") {
      await post($, "/reset").catch(() => {});
      return { text: "kernel reset" };
    }
    const ev = await runScript($, arg, maxCalls, next.signal);
    return { text: render(ev), exitCode: ev.status === "error" ? 1 : 0 };
  });
};
