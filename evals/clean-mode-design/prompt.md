---
name: clean-mode-design
runs: 3
max_turns: 8
allowed_tools: [Skill]
---

These are your own notes from today's ad-hoc chat about a session storage problem, jotted down before they evaporate from your brain:

context: every deploy = mass logout, we deploy like 4-6x/day now with the new pipeline so this is basically constant background pain, also the load balancer round-robins so two requests from the same user 200ms apart can hit different boxes that disagree on whether that user is logged in, we've been blaming "flaky auth" in incident channel for weeks and it's just this.

proposal (rough): redis, shared, one instance (or cluster? tbd), sessions move out of the per-process in-memory map into it. auth middleware currently owns a Map<sessionId, Session> basically, that whole thing gets swapped for calls into a new session-store module, get/set/delete, middleware itself barely changes shape.

things people brought up and we did NOT resolve:
- key naming — someone said prefix with a version so we're not stuck if the payload shape changes later (probably right)
- ttl / expiry — do we keep sliding expiry (touch on every request) or fixed window, sliding is what we have today i think but not 100% sure, need to check current cache eviction logic
- logout — needs to actually delete from redis obviously but also: do we need "log out everywhere" as a feature? nobody has asked for it but if we don't build a reverse index (user -> session ids) now it's annoying to bolt on later
- failure mode if redis is down — some people said treat as logged out (fail open? fail closed? i always mix these up), other people said no, that's insane, a blip would sign out the entire company, return a retry-able error instead
- rollout — the scary part is the cutover deploy itself, whatever we do can't ALSO sign everyone out, someone suggested a dual-write phase (write both places, read old, then flip reads over once redis has soaked) which seems obviously right but nobody's written it down properly
- also raised but out of scope for this doc i think: do we eventually want this same store for anything else, rate limiting keys or feature flag overrides have been mentioned as "hey redis is already there" ideas, not touching that now
- security person mentioned session ids are now "bearer tokens living in a shared store" and wants tls + auth on the redis connection + it not being reachable from the public internet, seems non negotiable

need someone to turn this into an actual doc before we start building, i think the bones are here but it's scattered across like 3 threads and a whiteboard photo.

Draft a short technical design document for the team to review before this work starts. Reply with only the document, nothing else.
