// decision-model's noun: typed decisions over a state, in the request/answer shape of TypeSafe's
// System One API. Any backend that answers this shape can serve it.

/** Pick one option; `criteria` maps option label to its rubric (`null` when the label says enough). */
export type DecisionChoiceQuestion = { type: "choice"; instructions: string; criteria: Record<string, string | null> };
/** Probability that a yes/no condition holds. */
export type DecisionNoulQuestion = { type: "noul"; instructions: string; criteria?: { true?: string; false?: string } };
/** Position on ordered levels, lowest first; at least two. */
export type DecisionScoreQuestion = { type: "score"; instructions: string; criteria: readonly string[] };
export type DecisionQuestion = DecisionChoiceQuestion | DecisionNoulQuestion | DecisionScoreQuestion;

export type DecisionChoiceAnswer = { type: "choice"; choice: string; probabilities: Record<string, number>; confidence: number };
export type DecisionNoulAnswer = { type: "noul"; noul: number };
export type DecisionScoreAnswer = { type: "score"; score: number; probabilities: Record<string, number>; confidence: number };
export type DecisionAnswer = DecisionChoiceAnswer | DecisionNoulAnswer | DecisionScoreAnswer;

export type DecisionRequest = {
  /** Text, or named fields rendered one per tag. */
  state: string | Record<string, unknown>;
  /** Questions under caller-chosen ids; answers come back under the same ids. */
  questions: Record<string, DecisionQuestion>;
  /** What the decision is for, shown in `/decision`'s log (e.g. "effort"). Not sent to the backend. */
  purpose?: string;
};
export type DecisionResult = {
  /** "system-one" (an endpoint speaking the protocol) or "claude" (the text judge). */
  backend: "system-one" | "claude";
  model: string;
  answers: Record<string, DecisionAnswer>;
};

export type Decision = {
  ask: (request: DecisionRequest) => Promise<DecisionResult>;
};

declare module "claude-code" {
  interface EngineInterface {
    decision: Decision;
  }
}
