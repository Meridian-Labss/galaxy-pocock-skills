# session-service

Handles auth sessions, per-user rate limiting, and feature flags for the API.
Everything here keeps its state in process memory today; see `src/`.
