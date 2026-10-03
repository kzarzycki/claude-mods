import { expect, test } from "claude-code/testing";

const cmd = (args: string) => ({ command: "cm", args, origin: { kind: "composer" as const }, presentation: { isFullscreen: false, columns: 120 } });
const rows = [
  { key: "cm-ttsr.questionRules", label: "Question rules", kind: "boolean", value: true, provider: { kind: "plugin", name: "cm-ttsr" }, isLocked: false },
  { key: "cm-effort.maxEffort", label: "Ceiling", kind: "choice", value: "xhigh", options: ["low", "high", "xhigh"], provider: { kind: "plugin", name: "cm-effort" }, isLocked: false },
  { key: "theme", label: "Theme", kind: "choice", value: "dark", provider: { kind: "core" }, isLocked: false },
];

test("/cm lists only cm-* rows and sets one by short name", async ($, on) => {
  const writes: unknown[] = [];
  on("config.list", () => ({ value: rows as never }));
  on("config.set", ($, e) => (writes.push(e), { value: e.value }));
  on("ui.invalidate", () => ({ value: undefined }));
  const listed = (await $.command.run(cmd("list"))).text ?? "";
  expect(listed).toContain("cm-ttsr.questionRules = true");
  expect(listed).not.toContain("theme");
  const out = await $.command.run(cmd("set questionRules off"));
  expect(out.text).toBe("cm-ttsr.questionRules = false");
  expect(writes).toEqual([{ key: "cm-ttsr.questionRules", value: false }]);
});
