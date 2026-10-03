// Shake, after oh-my-pi's compaction/shake.ts: drop heavy, recoverable content out of the live
// context with no model call. Tool output older than the protected tail is moved to a file and
// replaced by a one-line pointer the model can Read back.
//
// ponytail: tool output only, sized by chars/4. oh-my-pi also elides large fenced/XML blocks in
// message text and uses a tokenizer. Upgrade path: same pass over `text` for ``` and <tag> blocks.

import type { SessionMessage } from "claude-code";

export type Offload = { id: string; path: string; text: string };

const tokens = (s: string) => Math.ceil(s.length / 4);
const MIN_TOKENS = 400;

export function messageTokens(m: SessionMessage): number {
  let n = tokens(m.text);
  for (const u of m.toolUses) n += tokens(JSON.stringify(u.input ?? {})) + tokens(u.text ?? "");
  for (const r of m.toolResults ?? []) n += tokens(r.text);
  return n;
}

/**
 * Shake `messages`, keeping the newest `protectTokens` intact. `dir` is where offloaded text will
 * be written (by the caller); the pointers name files under it.
 */
export function shake(messages: readonly SessionMessage[], protectTokens: number, dir: string): { messages: SessionMessage[]; offloads: Offload[]; saved: number } {
  let tail = 0;
  let cut = messages.length;
  while (cut > 0 && tail + messageTokens(messages[cut - 1]!) <= protectTokens) tail += messageTokens(messages[--cut]!);

  const offloads: Offload[] = [];
  let saved = 0;
  const pointer = (id: string, text: string) => {
    const path = `${dir}/${id}.txt`;
    if (!offloads.some(o => o.id === id)) offloads.push({ id, path, text });
    const note = `[shaken: ${text.length} characters of tool output moved to ${path}; Read it if you need it]`;
    saved += tokens(text) - tokens(note);
    return note;
  };

  const out = messages.map((m, i) => {
    if (i >= cut) return m;
    let changed = false;
    const toolUses = m.toolUses.map(u => {
      if (!u.text || tokens(u.text) < MIN_TOKENS) return u;
      changed = true;
      const { result: _drop, ...rest } = u;
      return { ...rest, text: pointer(u.tool_use_id, u.text) };
    });
    const toolResults = m.toolResults?.map(r => {
      if (tokens(r.text) < MIN_TOKENS) return r;
      changed = true;
      const { result: _drop, ...rest } = r;
      return { ...rest, text: pointer(r.tool_use_id, r.text) };
    });
    if (!changed) return m;
    // Without its handle the engine rebuilds the message from role, text and the tool blocks.
    const { handle: _handle, ...plain } = m;
    return { ...plain, toolUses, ...(toolResults ? { toolResults } : {}) };
  });
  return { messages: out, offloads, saved };
}
