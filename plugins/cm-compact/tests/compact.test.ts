import type { On, SessionMessage } from "claude-code";
import { expect, test } from "claude-code/testing";

const big = "x".repeat(8000);
const history: SessionMessage[] = [
  { role: "user", text: "read the logs", toolUses: [], handle: "h0" },
  { role: "assistant", text: "", toolUses: [{ tool_use_id: "t1", tool: "Read", input: { file_path: "/a.log" }, text: big }], handle: "h1" },
  { role: "user", text: "", toolUses: [], toolResults: [{ tool_use_id: "t1", text: big, isError: false }], handle: "h2" },
  { role: "assistant", text: "the logs show a timeout", toolUses: [], handle: "h3" },
];

function host(on: On, written: Record<string, string>) {
  on("env.get", () => ({ value: "/home" }));
  on("session.id", () => ({ value: "s1" }));
  on("clock.now", () => ({ value: 7 }));
  on("fs.write", ($, e) => ((written[e.path] = e.text), { value: undefined }));
  on("ui.toast", () => ({ value: undefined }));
}

test("/compact shake moves old tool output to files and keeps the tail", { options: { protectTokens: 100 } }, async ($, on) => {
  const written: Record<string, string> = {};
  host(on, written);
  on("session.compact", () => ({ skip: "native compaction should not run" }));
  const r = await $.session.compact({ trigger: "manual", instructions: "shake", messages: history });
  expect(r.skip).toBeUndefined();
  const [m0, m1, m2, m3] = r.messages!;
  expect(m0).toEqual(history[0]);
  expect(m3).toEqual(history[3]);
  expect(m1!.handle).toBeUndefined();
  expect(m1!.toolUses[0]!.text).toContain("/home/.claude/cm-compact/s1/t1.txt");
  expect(m2!.toolResults![0]!.text).toContain("moved to");
  expect(written["/home/.claude/cm-compact/s1/t1.txt"]).toBe(big);
  if (r.skip === undefined) expect(r.tokensAfter!).toBeLessThan(r.tokensBefore!);
});

test("auto shake that can't save enough hands over to native", { options: { autoMethod: "shake", minSavings: 1_000_000 } }, async ($, on) => {
  host(on, {});
  let native = 0;
  on("session.compact", () => (native++, { skip: "native ran" }));
  const r = await $.session.compact({ trigger: "auto", messages: history });
  expect(native).toBe(1);
  expect(r.skip).toBe("native ran");
});

test("/compact handoff continues from the forked handoff document", async ($, on) => {
  const written: Record<string, string> = {};
  host(on, written);
  let prompt = "";
  on("model.fork", ($, e) => {
    prompt = e.prompt;
    return { value: { isAnswered: true, text: "## Goal\nShip it", usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } };
  });
  on("session.compact", () => ({ skip: "native compaction should not run" }));
  const r = await $.session.compact({ trigger: "manual", instructions: "handoff the flaky test", messages: history });
  expect(prompt).toContain("Additional focus: the flaky test");
  expect(r.messages).toHaveLength(1);
  expect(r.messages![0]!.text).toContain("<handoff>\n## Goal\nShip it\n</handoff>");
  expect(written["/home/.claude/cm-compact/s1/handoff-7.md"]).toBe("## Goal\nShip it");
});
