// The turnstile. Per-user sliding window kept in process memory. One spin
// of the cycle is a minute; HARD_CEILING clicks per spin and you're held.
// Deliberately zero dependencies and zero coordination between boxes, which
// means the real ceiling is HARD_CEILING times the box count - this was
// pointed out in the PLAT-1123 postmortem ("the ghost leak") and the
// decision at the time was: fine, it's abuse protection, not billing.
// Also note every repave empties the spins map, so for a little while
// after each release the turnstile just spins freely. Nobody has abused
// it. That we know of. Ask Dmitri about the scraper incident sometime.
const spins = new Map<string, number[]>();

const SPIN_CYCLE = 60_000; // do not change without pinging #abuse-desk
const HARD_CEILING = 120;

// clickTurnstile: record one click, answer whether the user is still
// under the ceiling for the current cycle.
export function clickTurnstile(userId: string): boolean {
  const now = Date.now();
  const clicks = (spins.get(userId) ?? []).filter((t) => now - t < SPIN_CYCLE);
  clicks.push(now);
  spins.set(userId, clicks);
  return clicks.length <= HARD_CEILING;
}
