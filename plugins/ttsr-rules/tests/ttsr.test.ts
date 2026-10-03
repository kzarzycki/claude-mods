import type { On } from "claude-code";
import { expect, test } from "claude-code/testing";
import { globToRegExp, matchToolRule, parseRule } from "../hooks/rules";

const NO_ANY = `---\ndescription: No any\ncondition: ":\\\\s*any\\\\b"\nscope: tool:edit(*.ts)\nglobs:\n  - "src/**"\n---\nUse unknown and narrow it.`;
const CLAIMS = `---\nquestion: Does the message claim tests pass without having run them?\n---\nRun the tests before saying they pass.`;

test("rule files parse the way oh-my-pi writes them", () => {
  const r = parseRule("no-any", "x", NO_ANY)!;
  expect(r.tools).toContain("Edit");
  expect(matchToolRule([r], "Edit", { file_path: "/p/src/a.ts", new_string: "let x: any = 1" }, "/p")?.match).toBe(": any");
  expect(matchToolRule([r], "Edit", { file_path: "/p/src/a.js", new_string: "let x: any" }, "/p")).toBeUndefined();
  expect(matchToolRule([r], "Edit", { file_path: "/p/lib/a.ts", new_string: "let x: any" }, "/p")).toBeUndefined();
  expect(matchToolRule([r], "Bash", { command: "x: any" }, "/p")).toBeUndefined();
  expect(globToRegExp("src/**/*.ts").test("src/c.ts")).toBe(true);
  expect(parseRule("q", "x", CLAIMS)?.question).toContain("claim tests pass");
  expect(parseRule("s", "x", `---\ncondition: foo\nscope: text\n---\nb`)).toBeUndefined();
});

/** Answer the session's file reads from an in-memory rule folder. */
function ruleFolder(on: On, files: Record<string, string>) {
  const dir = "/repo/.claude/ttsr";
  on("env.get", () => ({ value: "/home" }));
  on("fs.exists", ($, e) => ({ value: e.path === dir }));
  on("fs.list", () => ({ value: Object.keys(files).map(name => ({ name, kind: "file" as const, size: 1, mtimeMs: 0, isLink: false })) }));
  on("fs.read", ($, e) => ({ value: files[e.path.slice(dir.length + 1)] ?? "" }));
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("session.start", ($, e) => ({ cwd: e.cwd }));
}

// A stand-in for decision-model. The kit runs a test plugin's register on its own, without its closure,
// so it answers from the state alone: yes when the message mentions passing tests.
const fakeDecision = {
  name: "decision-model",
  register: (on: any) => {
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({}) } }));
    on("decision.ask", ($: unknown, e: { state: unknown; questions: Record<string, unknown> }) => {
      const noul = JSON.stringify(e.state).includes("tests pass") ? 0.9 : 0;
      return { value: { backend: "claude", model: "fake", answers: Object.fromEntries(Object.keys(e.questions).map(id => [id, { type: "noul", noul }])) } };
    });
  },
};

test("a matching tool call is denied with the rule as the reason", { plugins: [fakeDecision] }, async ($, on) => {
  ruleFolder(on, { "no-any.md": NO_ANY });
  on("ui.toast", () => ({ value: undefined }));
  let ran = 0;
  on("tool.call", () => (ran++, { result: "ok" }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  const denied = await $.tool.call({ tool: "Edit", file_path: "/repo/src/a.ts", old_string: "x", new_string: "let v: any" });
  expect(denied.deny).toContain('TTSR rule "no-any"');
  expect(denied.deny).toContain("Use unknown and narrow it.");
  const allowed = await $.tool.call({ tool: "Edit", file_path: "/repo/src/a.ts", old_string: "x", new_string: "let v: unknown" });
  expect(allowed.deny).toBeUndefined();
  expect(ran).toBe(1);
});

// The test kit does not route $.session.append to a test's on("session.append") (checked with a
// one-hook repro), so this asserts the toast; e2e/ttsr.sh checks the appended rule in a real session.
test("a question rule the judge says yes to fires after the turn", { plugins: [fakeDecision] }, async ($, on) => {
  ruleFolder(on, { "claims.md": CLAIMS });
  const toasts: string[] = [];
  on("ui.toast", ($, e) => (toasts.push(e.text), { value: undefined }));
  on("ui.log", () => ({ value: undefined }));
  on("turn.complete", ($, e) => ({ text: e.answer }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await $.turn.complete({ turnId: "t1", answer: "I refactored the parser.", durationMs: 1, isAborted: false, reason: "answer" });
  expect(toasts).toEqual([]);
  await $.turn.complete({ turnId: "t2", answer: "Done, all tests pass.", durationMs: 1, isAborted: false, reason: "answer" });
  expect(toasts).toEqual(["ttsr: claims"]);
});
