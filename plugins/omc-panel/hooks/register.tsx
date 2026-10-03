import type { ConfigRow, ConfigValue, EngineInterface, Register } from "claude-code";

// omc-panel: each omc-* mod's settings are already /config rows (`<plugin>.<field>`). This puts
// them in one place: a pane with a control per row, and `/omc set` for headless use.

const PANE = "omc-panel";

async function omcRows($: EngineInterface): Promise<ConfigRow[]> {
  return (await $.config.list()).filter(r => r.key.startsWith("omc-"));
}

/** Parse typed text into the row's kind. */
function parse(row: ConfigRow, text: string): ConfigValue {
  if (row.kind === "boolean") return /^(true|on|yes|1)$/i.test(text);
  if (row.kind === "number") return Number(text);
  return text;
}

async function set($: EngineInterface, row: ConfigRow, value: ConfigValue): Promise<string> {
  const r = await $.config.set({ key: row.key, value });
  $.ui.invalidate("ui.render");
  return r.deny !== undefined ? `${row.key}: refused (${r.deny})` : `${row.key} = ${JSON.stringify(r.value)}`;
}

const line = (r: ConfigRow) => `${r.key} = ${JSON.stringify(r.value)}${r.options ? `  [${r.options.join("|")}]` : ""}${r.isLocked ? "  (locked)" : ""}`;

export const register: Register = on => {
  on("session.start", async ($, e, next) => {
    await $.command.register({ name: "omc", description: "omc-panel: all oh-my-claude settings; `/omc set <key> <value>`", argumentHint: "[list | set <key> <value>]" });
    return next(e);
  });

  on("command.run", { command: "omc" }, async ($, e) => {
    const rows = await omcRows($);
    const m = /^set\s+(\S+)\s+([\s\S]+)$/.exec(e.args.trim());
    if (m) {
      const row = rows.find(r => r.key === m[1] || r.key.endsWith(`.${m[1]}`));
      if (!row) return { text: `no omc setting ${m[1]}`, exitCode: 1 };
      return { text: await set($, row, parse(row, m[2]!.trim())) };
    }
    if (e.args.trim() !== "list") {
      const placed = await $.ui.open({ id: PANE, title: "oh-my-claude", focus: true, closeOnEscape: true });
      if (placed.isPlaced) return { text: "oh-my-claude settings opened." };
    }
    return { text: rows.length ? rows.map(line).join("\n") : "no omc-* mods with settings are loaded" };
  });

  on("ui.render", { component: "Pane", requestId: PANE }, async ($, e) => {
    const rows = await omcRows($);
    if (e.surface !== "terminal") {
      const { Text } = $.ui.resolve(e);
      return <Text>{rows.map(line).join("\n")}</Text>;
    }
    const { Box, Text, Button, Select, Input } = $.ui.resolve(e);
    if (rows.length === 0) return <Text dimColor>No omc-* mods with settings are loaded.</Text>;
    return (
      <Box flexDirection="column">
        {rows.map(r => (
          <Box flexDirection="row" gap={1}>
            <Box width={34}>
              <Text wrap="truncate" dimColor={r.isLocked}>{r.key}</Text>
            </Box>
            {r.isLocked ? (
              <Text dimColor>{JSON.stringify(r.value)} (locked)</Text>
            ) : r.kind === "boolean" ? (
              <Button key={r.key} label={r.value ? "on" : "off"} onPress={() => void set($, r, !r.value)} />
            ) : r.options ? (
              <Select key={r.key} value={String(r.value)} options={r.options.map(o => ({ value: o }))} onSelect={(v: string) => void set($, r, v)} />
            ) : (
              <Input key={r.key} value={String(r.value)} placeholder={r.description} onSubmit={(v: string) => void set($, r, parse(r, v))} />
            )}
          </Box>
        ))}
      </Box>
    );
  });
};
