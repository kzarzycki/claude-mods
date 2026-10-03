import type { EngineInterface, Register } from "claude-code";

// eval-kernel: one `eval` tool backed by a long-lived Bun kernel (../kernel/kernel.ts) that keeps
// JavaScript state between cells. A cell's host calls (tool.X, completion, agent, tools) come back
// here as `call` events; this module runs them through $ and answers, so every tool a cell calls
// passes Claude Code's permission checks and every other plugin's hooks.

const TOOL = "eval";
const TOOL_ID = "mcp__eval-kernel__eval";

const DESCRIPTION = `Run JavaScript in a persistent Bun kernel, like a notebook cell.

- Top-level \`const\`/\`let\`/\`function\`/\`class\` declarations and \`import\`s at the start of a line persist into later cells. A trailing expression is the cell's value. Top-level await works.
- Bun, fetch and node:* modules are available. console.log and display(value) are captured.
- Claude Code tools: \`await tool.Read({ file_path })\` resolves to the tool's text and throws if the tool errors; \`tool.call(name, args, { raw: true })\` returns { text, result, isError } for any tool, MCP tools included. \`await tools()\` lists them. Calls go through the normal permission checks.
- Models and agents: \`await completion(prompt, { model: "haiku", system, maxTokens })\` returns text; \`await agent(prompt, { description, subagentType, model, schema })\` runs a subagent and returns its answer: the bare text, or with a JSON Schema \`schema\`, the parsed JSON value. Run several at once with Promise.all.
- Decisions: \`await judge({ type: "noul", instructions: "Is it risky?" }, state)\` asks the decision model (decision-model mod; Jev when configured) one typed question (\`noul\` yes-probability, \`choice\` with \`criteria\` {label: rubric}, \`score\` with ordered \`criteria\`) and returns its answer.
- Use it to fan work out (read 30 files, run 5 subagents, aggregate), to keep data between steps, or to compute instead of reasoning.
- Pass \`reset: true\` to restart the kernel with empty state.`;

type Event =
  | { status: "call"; callId: string; kind: string; payload: any }
  | { status: "done"; output: string; value?: string }
  | { status: "error"; output: string; error: string };

/** The kernel's socket; set once the session starts. */
let sock = "";
/** Subagents a running cell waits on: agentId → the kernel's callId and the schema its answer must match. */
const agentCalls = new Map<string, { callId: string; schema?: unknown }>();

/** Every subagent a cell started; their completion notices belong to the cell, not the parent. */
// ponytail: grows for the session's life (a few ids per agent() call).
const cellAgents = new Set<string>();

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

/** The answer a cell's agent() resolves to; with a schema, the parsed JSON. */
function agentAnswer(text: string, schema: unknown): { ok: true; value: unknown } | { ok: false; error: string } {
  if (schema === undefined) return { ok: true, value: text.trim() };
  // ponytail: parses only, no schema validation. Upgrade path: validate and send the subagent the errors to fix.
  try {
    return { ok: true, value: JSON.parse(text.trim().replace(/^```(?:json)?\s*|\s*```$/g, "")) };
  } catch {
    return { ok: false, error: `agent: the answer is not JSON: ${text.slice(0, 200)}` };
  }
}

async function post($: EngineInterface, path: string, body: unknown = {}): Promise<any> {
  const res = await $.http.fetch(`http://localhost${path}`, { method: "POST", socketPath: sock, body: JSON.stringify(body), headers: { "Content-Type": "application/json" } });
  return JSON.parse(res.text);
}

/** Wait (up to ~5 s) for the kernel to answer /health. */
async function ready($: EngineInterface): Promise<boolean> {
  for (let i = 0; i < 50; i++) {
    try {
      const res = await $.http.fetch("http://localhost/health", { socketPath: sock });
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
      for await (const chunk of $.process.spawn({ argv, cwd })) $.ui.log(`eval-kernel kernel: ${chunk.text.trimEnd()}`, { to: "debug" });
    } catch (err) {
      $.ui.log(`eval-kernel kernel failed to start: ${String(err)}`, { to: "debug" });
      await $.clock.sleep(1000);
    }
  }
}

/** Run one host call a cell made. Throws to make the cell's await reject. */
async function hostCall($: EngineInterface, kind: string, p: any): Promise<unknown> {
  if (kind === "tool") {
    if (p.tool === TOOL_ID) throw new Error("a cell can't call eval itself");
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
    // Optional: decision-model adds $.decision when it is loaded; eval-kernel works without it.
    type Ask = { decision: { ask: (r: object) => Promise<{ answers: Record<string, unknown> }> } };
    let r: { answers: Record<string, unknown> };
    try {
      r = await ($ as unknown as Ask).decision.ask({ purpose: "eval", state: p.state, questions: { q: p.question } });
    } catch (err) {
      if (err instanceof TypeError && /decision/.test(err.message)) throw new Error("judge() needs the decision-model mod");
      throw err;
    }
    return r.answers.q;
  }
  throw new Error(`unknown host call ${kind}`);
}

/** Run a cell to its end, answering its host calls. */
async function runCell($: EngineInterface, code: string, maxCalls: number, signal?: AbortSignal): Promise<Event> {
  if (!(await ready($))) return { status: "error", output: "", error: "the kernel is not running (is bun installed? see /eval)" };
  // An interrupt stops the cell: no request can be cancelled, so the kernel is reset, which ends the
  // wait below and drops the cell's pending subagent answers.
  // ponytail: interrupting loses kernel state. Upgrade path: an /interrupt endpoint that ends only the running cell.
  const interrupted = () => {
    agentCalls.clear();
    void post($, "/reset").catch(() => {});
  };
  signal?.addEventListener("abort", interrupted, { once: true });
  try {
    return await drive($, code, maxCalls, signal);
  } catch (err) {
    if (signal?.aborted) return { status: "error", output: "", error: "interrupted; the kernel was reset" };
    throw err;
  } finally {
    signal?.removeEventListener("abort", interrupted);
  }
}

async function drive($: EngineInterface, code: string, maxCalls: number, signal?: AbortSignal): Promise<Event> {
  let ev: Event = await post($, "/run", { code, cwd: await $.session.cwd() });
  let calls = 0;
  while (ev.status === "call") {
    if (signal?.aborted) return { status: "error", output: "", error: "interrupted; the kernel was reset" };
    if (++calls > maxCalls) {
      await post($, "/reset").catch(() => {});
      return { status: "error", output: "", error: `the cell made more than ${maxCalls} host calls; the kernel was reset` };
    }
    const { callId, kind, payload } = ev;
    if (kind === "agent") {
      // Answered later by the subagent's own turn.complete (below); meanwhile take the next event.
      try {
        const spawned = await $.agent.spawn({ prompt: agentPrompt(String(payload.prompt), payload.schema), description: String(payload.description ?? "eval cell subagent"), subagentType: payload.subagentType, model: payload.model });
        if (spawned.deny !== undefined || !spawned.agentId) throw new Error(spawned.deny ?? "no agent id");
        agentCalls.set(spawned.agentId, { callId, schema: payload.schema });
        cellAgents.add(spawned.agentId);
        ev = await post($, "/next");
      } catch (err) {
        ev = await post($, "/resume", { callId, ok: false, error: `agent: ${String(err)}` });
      }
      continue;
    }
    try {
      ev = await post($, "/resume", { callId, ok: true, value: await hostCall($, kind, payload) });
    } catch (err) {
      ev = await post($, "/resume", { callId, ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  }
  return ev;
}

function render(ev: Event): string {
  if (ev.status === "error") return [ev.output, `Error: ${ev.error}`].filter(Boolean).join("\n");
  if (ev.status === "done") return [ev.output, ev.value !== undefined ? `=> ${ev.value}` : ""].filter(Boolean).join("\n") || "(no output)";
  return "(cell still waiting)";
}

export const register: Register = (on, options) => {
  const bun = String(options.bun || "bun");
  const maxCalls = Number(options.maxCalls ?? 200);

  on("session.start", async ($, e, next) => {
    const id = await $.session.id();
    // Unix socket paths are capped near 104 bytes, so /tmp rather than the plugin's folder.
    sock = `/tmp/eval-kernel-${id.slice(0, 8)}-${Math.random().toString(36).slice(2, 8)}.sock`;
    void supervise($, [bun, `${$.plugin.root}/kernel/kernel.ts`, sock], e.cwd);
    await $.tool.register({
      name: TOOL,
      description: DESCRIPTION,
      inputSchema: {
        type: "object",
        properties: {
          code: { type: "string", description: "JavaScript to run as one cell" },
          title: { type: "string", description: "Short label for the cell" },
          reset: { type: "boolean", description: "Restart the kernel with empty state before running" },
        },
        required: ["code"],
      },
    });
    await $.command.register({ name: "eval", description: "eval-kernel kernel: `/eval vars`, `/eval reset`, or `/eval <code>` to run a cell yourself", argumentHint: "vars | reset | <code>" });
    return next(e);
  });

  on("tool.call", { tool: TOOL_ID }, async ($, e, next) => {
    const input = e as unknown as { code?: unknown; reset?: unknown };
    if (input.reset === true) {
      await post($, "/reset").catch(() => {});
      await $.clock.sleep(200);
    }
    if (typeof input.code !== "string" || !input.code.trim()) return input.reset === true ? { result: "kernel reset" } : { isError: true, result: "code is required" };
    const ev = await runCell($, input.code, maxCalls, next.signal);
    return ev.status === "error" ? { isError: true, result: render(ev) } : { result: render(ev) };
  });

  // A subagent hands its report back with the SubagentHandback tool; that report answers the
  // cell's agent() call.
  // ponytail: matched by hand because SubagentHandback is missing from this build's typed tool list.
  on("tool.call", async ($, e, next) => {
    const call = (e.tool as string) === "SubagentHandback" && e.agentId ? agentCalls.get(e.agentId) : undefined;
    if (e.agentId && call) {
      agentCalls.delete(e.agentId);
      const message = (e as unknown as { message?: unknown }).message;
      const answer = agentAnswer(typeof message === "string" ? message : JSON.stringify(message), call.schema);
      await post($, "/answer", { callId: call.callId, ...answer }).catch(() => {});
      // The cell is the recipient: answering the hand-back here keeps it out of the parent's
      // conversation, where each report would otherwise start a turn of its own.
      return { result: "Delivered to the eval cell that started you." };
    }
    return next(e);
  });

  // A cell's subagent runs in the background, so its end is also announced to the parent session,
  // which would spend a turn on each one. The cell already has the answer: drop those notices.
  on("prompt.submit", async ($, e, next) => {
    const ids = e.origin.kind === "task-notification" || e.origin.kind === "peer" || e.origin.kind === "peer-send-message" ? noticeAgents(e.text) : [];
    if (ids.length && ids.every(id => cellAgents.has(id))) return { drop: "eval-kernel: a cell's subagent finished; the cell has its answer" };
    return next(e);
  });

  // A subagent that ended without handing back: its final text (if any) answers the call.
  on("turn.complete", async ($, e, next) => {
    const call = e.agentId ? agentCalls.get(e.agentId) : undefined;
    if (e.agentId && call) {
      agentCalls.delete(e.agentId);
      const answer = e.reason === "answer" ? agentAnswer(e.answer, call.schema) : { ok: false, error: `subagent ended: ${e.reason}` };
      await post($, "/answer", { callId: call.callId, ...answer }).catch(() => {});
    }
    return next(e);
  });

  on("command.run", { command: "eval" }, async ($, e, next) => {
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
    const ev = await runCell($, arg, maxCalls, next.signal);
    return { text: render(ev), exitCode: ev.status === "error" ? 1 : 0 };
  });
};
