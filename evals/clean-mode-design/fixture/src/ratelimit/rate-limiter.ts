// Sliding window per user, kept in process memory. Deliberately simple: no
// external dependency, no cross-instance coordination.
const windows = new Map<string, number[]>();

const WINDOW_MS = 60_000;
const MAX_REQUESTS = 120;

export function checkRateLimit(userId: string): boolean {
  const now = Date.now();
  const timestamps = (windows.get(userId) ?? []).filter((t) => now - t < WINDOW_MS);
  timestamps.push(now);
  windows.set(userId, timestamps);
  return timestamps.length <= MAX_REQUESTS;
}

// NOTE: this map is empty again after every deploy, so a user's request
// count silently resets to zero on release. Nobody has complained yet
// because it just makes limits briefly generous, not broken.
