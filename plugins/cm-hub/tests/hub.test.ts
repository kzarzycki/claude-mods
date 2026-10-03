import { expect, test } from "claude-code/testing";

const cmd = (args: string) => ({ command: "hub", args, origin: { kind: "composer" as const }, presentation: { isFullscreen: false, columns: 120 } });

test("the hub tracks a subagent's model, turns and tokens and draws them in the pane", async ($, on) => {
  on("agent.list", () => ({ value: [{ id: "a1b2c3d4e5", description: "scan logs", type: "general-purpose", status: "completed" }] }));
  on("ui.open", () => ({ value: { isPlaced: false, reason: "headless" } }));
  on("turn.step", async function* ($, e) {
    return { turnId: e.turnId, index: e.index, answer: "found 3 timeouts", toolUses: [], stopReason: "end_turn" as const, usage: null };
  });
  on("turn.complete", ($, e) => ({ text: e.answer }));

  for await (const _ of $.turn.step({ turnId: "t", index: 0, model: "claude-haiku-4-5", messageCount: 1, agentId: "a1b2c3d4e5" })) {}
  await $.turn.complete({
    turnId: "t", agentId: "a1b2c3d4e5", answer: "found 3 timeouts", durationMs: 5, isAborted: false, reason: "answer",
    usage: { model: "claude-haiku-4-5", input_tokens: 100, output_tokens: 20, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
  });

  const listed = (await $.command.run(cmd("list"))).text ?? "";
  expect(listed).toContain("a1b2c3d4e5");
  expect(listed).toContain("claude-haiku-4-5");
  expect(listed).toContain("120 tok");
  expect(listed).toContain("completed");

  const ui = await $.ui.mount({
    plugin: "cm-hub", surface: "terminal", component: "Pane", requestId: "cm-hub",
    props: { title: "Agent hub", isFocused: true, bodyColumns: 100, placement: "dock", scroll: {} as never, view: {} as never },
  });
  const drawn = (await ui.findAll({ type: "Text" })).map(t => t.text).join("\n");
  expect(drawn).toContain("scan logs");
  expect(drawn).toContain("found 3 timeouts");
  expect(await ui.find({ key: "steer" })).toBeDefined();
  await ui.unmount();
});
