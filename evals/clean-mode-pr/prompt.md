---
name: clean-mode-pr
runs: 3
max_turns: 8
allowed_tools: [Skill]
---

You are wrapping up a bug fix and need to open a pull request. Here are your own rough notes, written right after you finished:

ok finally chased down that stupid invoice date bug. turns out formatDueDate() (billing/format-due-date.ts, remember this is the same file that also has the currency rounding hack from Q1, unrelated) was using local-tz date math instead of doing everything in UTC. classic. customers on the west coast (and I guess literally anyone UTC-1 or worse) would see e.g. 03-01 render as 02-28, off by exactly one day, which obviously screws with the "due in 3 days" reminder email logic too (didn't touch that, flagging for later, might be its own bug — see also the reminder-cron flakiness thread from last week, could be related, could not be).

anyway swapped the local getters for the UTC ones (~6 loc), wrote format-due-date.test.ts with a UTC-8 case that repros it on main and goes green after, ran the whole billing suite locally just to be safe (42 green). didn't touch the reminder email stuff, didn't touch the currency rounding thing even though I was staring right at it, resisted the urge. also there's a preexisting TODO in that file about extracting a shared date-utils module, still not doing that today, not in scope.

need this in before the end of week release cut ideally. someone should double check the UTC-8 boundary case is actually the worst case though, I *think* it is but haven't proven it for say UTC-12 vs UTC+14 stuff, feels like it shouldn't matter since we're just formatting not computing new dates but flag if you think otherwise.

Turn this into the pull request title and description you would actually post for review. Reply with only the PR title and description, nothing else.
