import flags from "./flags.json";

// Loaded once at process start. Flipping a flag today means editing this
// file and shipping a deploy like any other code change.
const flagState: Record<string, boolean> = { ...flags };

export function isEnabled(flagName: string): boolean {
  return flagState[flagName] ?? false;
}

// TODO: product keeps asking to flip flags without a deploy, especially for
// killing a bad rollout fast. Nothing here supports that yet.
