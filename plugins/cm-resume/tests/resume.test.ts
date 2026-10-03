import { expect, test } from "claude-code/testing";

// A stand-in for cm-decision that always says yes. The kit runs a test plugin's register on its
// own, without its closure, so the answer is written into the hook.
const fakeDecision = {
  name: "cm-decision",
  register: (on: any) => {
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({}) } }));
    on("decision.ask", () => ({ value: { backend: "claude", model: "fake", answers: { stop: { type: "noul", noul: 0.9 } } } }));
  },
};

test("an unexpected stop gets one resume prompt", { plugins: [fakeDecision] }, async ($, on) => {
  const submitted: string[] = [];
  on("ui.toast", () => ({ value: undefined }));
  on("prompt.submit", ($, e) => {
    submitted.push(e.text);
    return { text: e.text };
  });
  on("turn.step", async function* ($, e) {
    return { turnId: e.turnId, index: e.index, answer: "Let me run the tests next.", toolUses: [], stopReason: "end_turn" as const, usage: null };
  });
  on("turn.complete", ($, e) => ({ text: e.answer }));
  const complete = (turnId: string) => $.turn.complete({ turnId, answer: "Let me run the tests next.", durationMs: 1, isAborted: false, reason: "answer" });
  for await (const _ of $.turn.step({ turnId: "t1", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t1");
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t2");
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toContain("Carry on");
});
