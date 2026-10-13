# Rate limits reset on every deploy

Deploys restart the API pods, which clears the in-memory counters.

- Users can exceed their hourly quota right after a deploy.
- Fix: move counters to Redis.
