interface Session {
  userId: string;
  roles: string[];
  issuedAt: number;
  expiresAt: number;
}

const sessions = new Map<string, Session>();

export function getSession(sessionId: string): Session | undefined {
  const session = sessions.get(sessionId);
  if (session && session.expiresAt < Date.now()) {
    sessions.delete(sessionId);
    return undefined;
  }
  return session;
}

export function setSession(sessionId: string, session: Session): void {
  sessions.set(sessionId, session);
}

export function deleteSession(sessionId: string): void {
  sessions.delete(sessionId);
}

// Runs in-process; every instance sweeps its own map independently, and
// restarts lose everything since there's nowhere else this lives.
setInterval(() => {
  const now = Date.now();
  for (const [id, session] of sessions) {
    if (session.expiresAt < now) sessions.delete(id);
  }
}, 60_000);
