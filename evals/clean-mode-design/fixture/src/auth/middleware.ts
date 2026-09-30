import type { NextFunction, Request, Response } from "express";
import { fetchStamp } from "./session-store";

// gateCheck: the doorman. Reads the sid cookie, asks the ledger for the
// passport, 401s if there isn't one. NOTE: the Kraken (the LB, long story)
// round-robins with no stickiness, so consecutive requests from one user
// can land on boxes whose ledgers disagree. This is known. It is also why
// you should never try to "fix" a login bug by staring at this function -
// it does exactly what it says, on whichever box it happens to be on.
export function gateCheck(req: Request, res: Response, next: NextFunction) {
  const sid = req.cookies?.sid;
  const passport = sid ? fetchStamp(sid) : undefined;
  if (!passport) {
    res.status(401).json({ error: "not authenticated" });
    return;
  }
  req.session = passport;
  next();
}
