---
name: clean-mode-migration
runs: 3
max_turns: 12
model: claude-sonnet-5
allowed_tools: [Skill, Task, Agent]
---

You own the integration with our payments provider. They are retiring their v1 API and you need to write the design doc the team will work from. Here is everything you have: the provider's migration email, plus your own notes from the call with their solutions engineer.

from the provider:

"v2 is live from 15 Nov 2026. v1 is supported until 31 Mar 2027, both run side by side until then. Note the API key cutoff is EARLIER than the v1 sunset - query-string API keys stop working 15 Jan 2027, after that it's Bearer tokens only, so you cannot wait until March. Tokens expire after 24h, refresh via POST /auth/refresh.

Field changes on every resource: customer_id becomes account_id. created becomes created_at and is ISO-8601 UTC (it was a unix int). Money fields move from float dollars to integer cents, and currency is now required on write - it used to default to USD silently. The status enum drops pending and adds authorized and captured; existing pending rows map to authorized.

Errors: v1 returned HTTP 200 with {err_msg: "..."} in the body. v2 returns real status codes and {error: {code, message}}. Rate limits go from 100/min per key to 1000/min per account - note that's per account now, not per key, so if you're fanning out across keys you will see a drop. 429s include Retry-After.

Pagination is cursor-based; page and per_page are gone. Max page size is 500, down from 1000. List endpoints no longer inline the nested customer object - you get account_id and fetch separately if you need it.

Webhooks are signed HMAC-SHA256 in X-Signature-V2. The old X-Signature header is removed at sunset, not before, so you can verify both during the overlap. Retries are 5 attempts with exponential backoff. Sandbox moves to sandbox-v2.provider.com.

New: idempotency keys are required on all POSTs, retained 24h. There's a batch endpoint capped at 100 items. And /reports is deleted outright - it's replaced by an async export job you poll at /exports/{id}.

SDKs: Node >=4.0 and Python >=3.0 are out now. Ruby isn't supported until Q2 2027."

my notes from the call:

ok so a few things that aren't in their email. PII fields (name, email, address) now need an explicit scope on the token, default tokens won't return them, which will silently break our invoice rendering if we miss it - they said it returns nulls, NOT an error, so we won't notice until a customer complains. audit log retention goes 90 days to 400 days which is actually good for us, compliance has been asking.

Northwind are on a bespoke contract from the acquisition and their account can't be migrated by the normal path, provider has to do it manually and wants 6 weeks notice, so that's the long pole and nobody has told them yet.

our own dates: staging cutover 1 Dec 2026, prod 10 Jan 2027 (just before the key cutoff, deliberately). rollback window is 72h after prod cutover, after that they purge the v1 shadow data and we're committed. support need a comms draft two weeks before each cutover, that's on us not them.

also the Ruby thing matters - the reconciliation worker is Ruby. Either we port it or we leave it on v1 until Q2 and it breaks at the key cutoff in January, which is before Ruby support lands. Nobody has an answer for that yet.

Write the technical design document the team will work from for this migration. Reply with only the document, nothing else.
