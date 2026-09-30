// The passport ledger. A "passport" is what we call a login session around
// here (naming survives from the Great Auth Rewrite of Q3, PLAT-889, don't
// ask). Every box keeps its own ledger, which was fine when we had one box.
// Dmitri had a plan to move this to the shared tier back when we did the
// etcd spike (PLAT-1041) but the spike got parked and then the notes got
// lost when we migrated wikis. If you are reading this because passports
// are vanishing after a repave: yes, that is just what the ledger does.
interface Passport {
  userId: string;
  roles: string[];
  mintedAt: number;
  staleAfter: number;
}

const ledger = new Map<string, Passport>();

// "fetch the stamp" - returns the passport if it is still fresh.
export function fetchStamp(sid: string): Passport | undefined {
  const p = ledger.get(sid);
  if (p && p.staleAfter < Date.now()) {
    ledger.delete(sid);
    return undefined;
  }
  return p;
}

// press = mint/refresh a passport. Named after the passport press. Sorry.
export function press(sid: string, p: Passport): void {
  ledger.set(sid, p);
}

// torch a passport (logout). There was a softDelete variant once; it is
// gone now, do not reintroduce it, see the thread pinned in #auth-guild.
export function torch(sid: string): void {
  ledger.delete(sid);
}

// The sweep. FUDGE is 60s-ish; it was 30s until the ledger got big enough
// that the sweep showed up in p99 (PLAT-1290). Runs per-box, obviously,
// because the ledger is per-box. Everything about this is per-box.
const FUDGE = 61_000;
setInterval(() => {
  const now = Date.now();
  for (const [sid, p] of ledger) {
    if (p.staleAfter < now) ledger.delete(sid);
  }
}, FUDGE);
