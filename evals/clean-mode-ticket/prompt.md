---
name: clean-mode-ticket
runs: 3
max_turns: 12
model: claude-sonnet-5
allowed_tools: [Skill, Task, Agent]
---

Someone forwarded you this from #support-escalations, and you need to turn it into a ticket:

forwarding this up from #support-escalations, seems like it's become a recurring thing:

"hey another customer today (this is like the 4th one this week?) asking why they can't get their invoices as a csv, they want to dump them into their own accounting tool apparently a lot of them use xero or quickbooks or whatever and just want raw rows. right now we tell them to screenshot the table lol which is obviously not great. can we just add an export button to the billing settings page?"

heads up though — need to be careful here, this touches PII/financial data so whatever we build needs a real auth check, i.e. server derives the customer from the session, does NOT trust a customer id passed from the client (we got bitten by exactly this pattern before on the /reports endpoint, see incident-118 postmortem if you want the gory details).

rough shape as i see it: new trpc procedure that pulls invoices for the logged in customer, dump to csv (need to figure out escaping for the description field since some customers apparently put commas and quotes in their invoice notes), wire a download button into the existing billing settings page next to the current invoice table.

no hard deadline from leadership but support keeps flagging it in the weekly sync so would be good to land before EOQ. also somebody asked if we should support xlsx too but i think that's scope creep, csv only for v1 unless someone pushes back. oh also: what happens for a customer with literally zero invoices, don't want that to just 500.

Write the work ticket you would file for this piece of work. Reply with only the ticket, nothing else.
