import { expect, test } from "claude-code/testing";

const cmd = (args: string) => ({ command: "omc", args, origin: { kind: "composer" as const }, presentation: { isFullscreen: false, columns: 120 } });
const rows = [
  { key: "omc-jev.autoEffort", label: "Auto effort", kind: "boolean", value: true, provider: { kind: "plugin", name: "omc-jev" }, isLocked: false },
  { key: "omc-jev.maxEffort", label: "Ceiling", kind: "choice", value: "xhigh", options: ["low", "high", "xhigh"], provider: { kind: "plugin", name: "omc-jev" }, isLocked: false },
  { key: "theme", label: "Theme", kind: "choice", value: "dark", provider: { kind: "core" }, isLocked: false },
];

test("/omc lists only omc-* rows and sets one by short name", async ($, on) => {
  const writes: unknown[] = [];
  on("config.list", () => ({ value: rows as never }));
  on("config.set", ($, e) => (writes.push(e), { value: e.value }));
  on("ui.invalidate", () => ({ value: undefined }));
  const listed = (await $.command.run(cmd("list"))).text ?? "";
  expect(listed).toContain("omc-jev.autoEffort = true");
  expect(listed).not.toContain("theme");
  const out = await $.command.run(cmd("set autoEffort off"));
  expect(out.text).toBe("omc-jev.autoEffort = false");
  expect(writes).toEqual([{ key: "omc-jev.autoEffort", value: false }]);
});
