---
name: clean-mode
description: Use clean mode when creating or editing durable human-facing project artifacts, including technical designs, work tickets, pull requests, documentation, and code comments. Put important information first and make the result easy to speed-read and discuss.
---

Clean mode is the default for durable human-facing project artifacts. Write so a human can speed-read and understand the important information with minimal context. Use these steps:

## Step 1. Follow these general principles

This document follows its own rules. Treat its shape as the target register.

### Be terse

- Be extremely concise. Use the fewest words possible. Freely use ungrammatical note-taking language.
- Cut hedging and throat-clearing ("worth noting", "this is not X, it's Y") and phrases that do not aid understanding.
- Never restate a point already made.

### Structure for scanning

A reader should get the meaning by moving their eyes down the page, not by reading every line.

- Break up any paragraph that runs more than 3 sentences long.
- Use short, meaningful subtitles so a reader can find the section they need.
- Use bullet points or numbered lists for parallel items, including comma-delimited runs inside a sentence.
- Never use bold to mark structure: not as a dot point lead-in, not as a field label (`**Title:**`, `**Status:**`, `**Summary:**`), not as a stand-in for a heading. A multi-sentence item gets a `###` subheading, a short one gets a plain bullet or a plain line.

### Order and language

- Put the core information at the top; move complex detail to the bottom or into an attached document.
- Use simple titles and section headings that are easy to remember and discuss.
- Headings state the section's point in plain words ("Rate limits reset on every deploy"), never a metaphor or a mood ("a quiet hole", "visible pain").
- Prefer familiar language over jargon, technical terms, and code identifiers that require lookup.
- Give files meaningful names that indicate their contents.

### Translate source terminology into plan language

A document inherits the register of whatever it was written from. Write in the reader's language, not the source's.

- Replace in-house nicknames and code identifiers with plain terms. If people will need the code name, map it once ('the mail queue - "the outbox" in the code') and use the plain term from then on.
- State each fact in plain words; the reader must never need to open a citation to follow a sentence.
- Leave the source's asides, history, and contextual detail behind; carry over *only* what the reader needs.
- Explain a necessary technical term the first time it appears, in a clause, not a glossary. Terms the document is about need no explanation.

## Step 2. Review and correct

Before finishing, use a subagent to critically review what you have written, based on these guidelines:

- Is this longer than it needs to be? Can it be a bit more concise?
- Can a human understand the important point from the top of the document? 
- Can they find the section they need by scanning headings and lists?
- Does every detail earn its place, or should it move below the fold or into a separate reference?
- Can a reader get what they need without wading through superfluous detail?
- Could a newly hired teammate with little or no context follow every sentence?

Then update the document if the findings would result in a document that better conforms to the principles outlined in this skill.
