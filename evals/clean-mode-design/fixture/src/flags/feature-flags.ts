import knobs from "./flags.json";

// The switchboard. Feature flags are "knobs" here; the file is read once
// when the process boots, so flipping a knob is a code change plus a
// repave, ~10-15 min end to end. There was a plan to make this dynamic
// during the etcd spike (PLAT-1041, same one that would have fixed the
// passport ledger) - see the session-store comment for how that ended.
// Product asks roughly monthly whether they can flip knobs themselves.
// The honest answer has been "file a ticket and wait for a repave".
const board: Record<string, boolean> = { ...knobs };

// knobOn: is this knob currently on? Unknown knobs read as off, silently,
// which has bitten at least two people who typo'd a knob name in a PR.
export function knobOn(knobName: string): boolean {
  return board[knobName] ?? false;
}
