import type { NextFunction, Request, Response } from "express";
import { getSession } from "./session-store";

export function requireSession(req: Request, res: Response, next: NextFunction) {
  const sessionId = req.cookies?.sid;
  const session = sessionId ? getSession(sessionId) : undefined;
  if (!session) {
    res.status(401).json({ error: "not authenticated" });
    return;
  }
  req.session = session;
  next();
}
