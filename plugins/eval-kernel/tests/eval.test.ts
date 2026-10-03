import type { On } from "claude-code";
import { expect, test } from "claude-code/testing";

// The kernel itself is checked by kernel/kernel.check.ts. Here a fake kernel answers http.fetch,
// so this covers the mod's half: the call/resume loop and how each host call is run.

type Ev = Record<string, unknown>;

/** Start the session against a fake kernel whose /run and /resume replies come from `script`. */
async function start($: any, on: On, script: (path: string, body: any) => Ev) {
  const posts: { path: string; body: any }[] = [];
  on("session.id", () => ({ value: "abcdef123456" }));
  on("tool.register", ($, e) => ({ value: { tool: `mcp__eval-kernel__${e.name}` } }));
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("process.spawn", async function* () {
    return { value: { code: 0, signal: null } };
  });
  on("clock.sleep", () => ({ value: undefined }));
  on("session.cwd", () => ({ value: "/repo" }));
  on("http.fetch", ($, e) => {
    const path = new URL(e.url).pathname;
    const body = e.init?.body ? JSON.parse(e.init.body) : undefined;
    if (path !== "/health") posts.push({ path, body });
    const reply = path === "/health" ? { ok: true } : script(path, body);
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify(reply) } };
  });
  on("session.start", ($, e) => ({ cwd: e.cwd }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  return posts;
}

test("a cell's tool call runs through $.tool.call and its result resumes the cell", async ($, on) => {
  on("tool.call", { tool: "Read" }, ($, e) => ({ result: `contents of ${e.file_path}` as never, text: `contents of ${e.file_path}` }));
  const posts = await start($, on, (path, body) =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Read", args: { file_path: "/repo/a.ts" } } } : { status: "done", output: "", value: JSON.stringify(body.value) },
  );
  const r = await $.tool.call({ tool: "mcp__eval-kernel__eval", code: "await tool.Read({ file_path: '/repo/a.ts' })" });
  expect(r.isError).toBeUndefined();
  expect(String(r.result)).toContain("contents of /repo/a.ts");
  expect(posts[0]).toEqual({ path: "/run", body: { code: "await tool.Read({ file_path: '/repo/a.ts' })", cwd: "/repo" } });
  expect(posts[1]!.body).toMatchObject({ callId: "c1", ok: true, value: { text: "contents of /repo/a.ts", isError: false } });
});

test("a cell may not call eval itself, and the refusal reaches the cell as an error", async ($, on) => {
  const posts = await start($, on, path =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "mcp__eval-kernel__eval", args: { code: "1" } } } : { status: "error", output: "", error: "Error: a cell can't call eval itself" },
  );
  const r = await $.tool.call({ tool: "mcp__eval-kernel__eval", code: "await tool.call('mcp__eval-kernel__eval', { code: '1' })" });
  expect(r.isError).toBe(true);
  expect(posts[1]!.body).toMatchObject({ callId: "c1", ok: false, error: "a cell can't call eval itself" });
});

// agent() isn't covered here: the agent id comes only from core (a test hook answering
// agent.spawn starts no subagent and gets none), so e2e/eval.sh covers it with a real one.
