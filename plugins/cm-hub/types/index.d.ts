export type HubAgent = {
  id: string;
  description: string;
  type: string;
  status: string;
  model?: string;
  turns: number;
  tokens: number;
  /** The tail of its latest answer. */
  last?: string;
};

declare module "claude-code" {
  interface PluginState {
    "cm-hub": { agents: HubAgent[]; selected: string; sent: string };
  }
}
