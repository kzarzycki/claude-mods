import { expect, test } from "claude-code/testing";

// A stand-in for cm-decision. The kit runs a test plugin's register on its own, without its
// closure, so the answer is written into the hook.
const fakeDecision = {
  name: "cm-decision",
  register: (on: any) => {
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({}) } }));
    on("decision.ask", () => ({ value: { backend: "claude", model: "fake", answers: { effort: { type: "choice", choice: "xhigh", probabilities: { xhigh: 1 }, confidence: 1 } } } }));
  },
};

const stepResult = (turnId: string, index: number) => ({ turnId, index, answer: "ok", toolUses: [{ name: "Read", input: {} }], stopReason: "tool_use" as const, usage: null });

test("the decided level is the effort of every main-thread step of that turn", { plugins: [fakeDecision] }, async ($, on) => {
  const efforts: unknown[] = [];
  on("prompt.submit", ($, e) => ({ text: e.text }));
  on("ui.status", () => ({ value: undefined }));
  on("turn.step", async function* ($, e) {
    efforts.push(e.effort);
    return stepResult(e.turnId, e.index);
  });
  await $.prompt.submit({ text: "why does the cache go stale under load?", wait: false, origin: { kind: "composer" } });
  for (const index of [0, 1]) for await (const _ of $.turn.step({ turnId: "t1", index, model: "opus", messageCount: 1 })) {}
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  expect(efforts).toEqual(["xhigh", "xhigh", undefined]);
});
