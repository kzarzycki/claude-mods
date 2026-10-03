import { atom, read, update } from "claude-code";
import type { EngineInterface, Register } from "claude-code";
import type { HubAgent } from "../types";

// cm-hub: one place to watch and steer this session's subagents.
// - The list is $.agent.list, plus what hooks see: the model and turns from turn.step, tokens and
//   the latest answer from turn.complete (AgentInfo carries neither).
// - Steering is $.session.append to the subagent's loop; it reads the note at its next step.

const PANE = "cm-hub";
const agents = atom({ plugin: "cm-hub", key: "agents" } as const, []);
const selected = atom({ plugin: "cm-hub", key: "selected" } as const, "");
const sent = atom({ plugin: "cm-hub", key: "sent" } as const, "");

const blank = (id: string): HubAgent => ({ id, description: "", type: "", status: "running", turns: 0, tokens: 0 });

/** Merge $.agent.list into what the hooks have seen. */
async function refresh($: EngineInterface) {
  const listed = await $.agent.list();
  await update($, agents, seen =>
    listed.map(a => ({ ...(seen.find(s => s.id === a.id) ?? blank(a.id)), description: a.description, type: a.type, status: a.status })),
  );
}

async function patch($: EngineInterface, id: string, change: (a: HubAgent) => HubAgent) {
  await update($, agents, list => (list.some(a => a.id === id) ? list : [...list, blank(id)]).map(a => (a.id === id ? change(a) : a)));
}

async function steer($: EngineInterface, id: string, text: string): Promise<string> {
  const r = await $.session.append({ agentId: id, message: { type: "user", content: [{ type: "text", text: `Message from the person running this session: ${text}` }] } });
  return r.deny !== undefined ? `not sent: ${r.deny}` : `sent to ${id}`;
}

const table = (list: HubAgent[]) =>
  list.length === 0
    ? "no subagents in this session"
    : list.map(a => `${a.id}  ${a.status.padEnd(9)} ${(a.model ?? "?").padEnd(16)} ${String(a.turns).padStart(3)} turns ${String(a.tokens).padStart(8)} tok  ${a.type}: ${a.description}`).join("\n");

export const register: Register = on => {
  on("session.start", async ($, e, next) => {
    await $.command.register({ name: "hub", description: "cm-hub: subagents pane; `/hub list`, `/hub send <agent id> <message>`", argumentHint: "[list | send <id> <message>]" });
    return next(e);
  });

  on("turn.step", async function* ($, e, next) {
    if (e.agentId) await patch($, e.agentId, a => ({ ...a, model: e.model, status: "running" }));
    return yield* next(e);
  });

  on("turn.complete", async ($, e, next) => {
    if (e.agentId) {
      const u = e.usage;
      const used = u ? u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0;
      await patch($, e.agentId, a => ({ ...a, turns: a.turns + 1, tokens: a.tokens + used, last: e.answer.slice(-200) || a.last }));
      await refresh($);
    }
    return next(e);
  });

  // A finished Agent tool call is a new agent (or a done one): refresh the list.
  on("tool.call", { tool: "Agent" }, async ($, e, next) => {
    const r = await next(e);
    await refresh($);
    return r;
  });

  on("command.run", { command: "hub" }, async ($, e) => {
    await refresh($);
    const send = /^send\s+(\S+)\s+([\s\S]+)$/.exec(e.args.trim());
    if (send) {
      const id = (await read($, agents)).find(a => a.id.startsWith(send[1]!))?.id ?? send[1]!;
      return { text: await steer($, id, send[2]!) };
    }
    if (e.args.trim() === "list") return { text: table(await read($, agents)) };
    const placed = await $.ui.open({ id: PANE, title: "Agent hub", focus: true, closeOnEscape: true });
    // Headless there is nowhere to put a pane: print the table instead.
    return { text: placed.isPlaced ? "Agent hub opened." : table(await read($, agents)) };
  });

  on("ui.render", { component: "Pane", requestId: PANE }, async ($, e) => {
    const list = await read($, agents);
    if (e.surface !== "terminal") {
      // ponytail: steering controls are drawn on the terminal only; other surfaces get the table.
      const { Text } = $.ui.resolve(e);
      return <Text>{table(list)}</Text>;
    }
    const { Box, Text, Select, Input } = $.ui.resolve(e);
    const pick = (await read($, selected)) || list[0]?.id || "";
    const note = await read($, sent);
    const width = e.props.bodyColumns;
    return (
      <Box flexDirection="column">
        {list.length === 0 && <Text dimColor>No subagents yet. They appear here as they start.</Text>}
        {list.map(a => (
          <Box flexDirection="column">
            <Text bold={a.id === pick} color={a.status === "running" ? "green" : undefined} wrap="truncate">
              {a.id === pick ? "▸ " : "  "}
              {a.status.padEnd(9)} {(a.model ?? "").padEnd(14)} {a.turns}t {a.tokens}tok {a.type}: {a.description}
            </Text>
            {a.last && <Text dimColor wrap="truncate">{"    " + a.last.replace(/\s+/g, " ").slice(0, Math.max(10, width - 6))}</Text>}
          </Box>
        ))}
        {list.length > 0 && (
          <Select key="pick" label="Agent" value={pick} options={list.map(a => ({ value: a.id, label: `${a.id.slice(0, 8)} ${a.description}` }))} onSelect={(v: string) => void update($, selected, () => v)} />
        )}
        {pick && (
          <Input
            key="steer"
            label="Steer"
            placeholder={`message to ${pick.slice(0, 8)}`}
            submitLabel="Send"
            onSubmit={async (text: string) => {
              if (!text.trim()) return;
              const result = await steer($, pick, text);
              await update($, sent, () => `${text.slice(0, 50)} (${result})`);
            }}
          />
        )}
        {note && <Text dimColor>last sent: {note}</Text>}
      </Box>
    );
  });
};
