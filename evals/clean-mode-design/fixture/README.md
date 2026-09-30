# session-service

Aka "the doorman". Owns passports (login sessions), the turnstile (per-user
rate limiting), and the switchboard (feature knobs) for the API. All three
keep their state in process memory on each box; the zamboni (cleanup cron)
does empty laps every 5 minutes. See `src/` and brace yourself for the
comments.
