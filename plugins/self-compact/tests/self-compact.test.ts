import { expect, test } from "claude-code/testing";

// A stand-in for decision-model that says every turn ends a task. The kit runs a test plugin's
// register on its own, without its closure, so the answer is written into the hook.
const finishedTasks = {
  name: "decision-model",
  register: (on: any) => {
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({}) } }));
    on("decision.ask", () => ({ value: { backend: "claude", model: "fake", answers: { done: { type: "noul", noul: 0.9 } } } }));
  },
};

declare const setTimeout: (f: () => void, ms: number) => unknown;
const settle = () => new Promise<void>(r => setTimeout(r, 20));

function session(on: any, percent: number) {
  const compacts: unknown[] = [];
  const prompts: string[] = [];
  on("tool.register", ($: unknown, e: any) => ({ value: { tool: `mcp__self-compact__${e.name}` } }));
  on("session.start", ($: unknown, e: any) => ({ cwd: e.cwd }));
  on("session.usage", () => ({ value: { startedAt: 0, context: { percent }, rateLimits: {}, cost: {} } }));
  on("ui.toast", () => ({ value: undefined }));
  on("command.run", ($: unknown, e: any) => (compacts.push(e.args), { text: "" }));
  on("prompt.submit", ($: unknown, e: any) => (prompts.push(e.text), { text: e.text }));
  on("turn.complete", ($: unknown, e: any) => ({ text: e.answer }));
  return { compacts, prompts };
}
const complete = ($: any, answer: string) => $.turn.complete({ turnId: "t", answer, durationMs: 1, isAborted: false, reason: "answer" });

test("the model's request compacts once the turn ends, with its focus", async ($, on) => {
  const s = session(on, 30);
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await $.tool.call({ tool: "mcp__self-compact__compact_after_turn", focus: "the API plan" } as never);
  expect(s.compacts).toEqual([]);
  await complete($, "Done: the endpoint is in.");
  await settle();
  expect(s.compacts).toEqual(["the API plan"]);
});

test("a finished task in a full context gets one nudge; declining it compacts nothing", { plugins: [finishedTasks] }, async ($, on) => {
  const s = session(on, 80);
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await complete($, "All tests pass; the fix is merged.");
  await settle();
  expect(s.prompts).toHaveLength(1);
  expect(s.prompts[0]).toContain("80% full");
  await complete($, "continue");
  await settle();
  expect(s.prompts).toHaveLength(1);
  expect(s.compacts).toEqual([]);
});

test("without a decision model the nudge rearms only after growth or turns", async ($, on) => {
  const s = session(on, 80);
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await complete($, "Done.");
  await complete($, "continue");
  await complete($, "Done again.");
  await settle();
  expect(s.prompts).toHaveLength(1);
});

test("below the threshold nothing happens", { plugins: [finishedTasks] }, async ($, on) => {
  const s = session(on, 40);
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await complete($, "Done.");
  await settle();
  expect(s.prompts).toEqual([]);
  expect(s.compacts).toEqual([]);
});
