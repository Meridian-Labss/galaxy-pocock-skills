---
name: clean-mode
description: Use clean mode when creating or editing durable human-facing project artefacts, including technical designs, work tickets, pull requests, documentation, and code comments. Put important information first and make the result easy to speed-read and discuss.
---

Clean mode is the default for durable human-facing project artefacts. Write so a human can speed-read and understand the important information with minimal context.

## General principles

- Put the core information at the top. Move complex detail below the fold or into an attached document.
- Use simple titles and section headings that are easy to remember and discuss.
- Prefer familiar language over jargon, technical terms, and code identifiers that require lookup.
- Use short, meaningful subtitles so a reader can find the section they need. Avoid walls of text: break up any paragraph that runs several sentences long.
- Use bullet points or numbered lists for parallel items, even when each item would otherwise open with a bold label. A paragraph per item is not a list, no matter how it is formatted.
- State each point once and stop. Cut hedging and throat-clearing ("worth noting", "one correction to the sketch", "this is not X, it's Y"), self-congratulatory comparisons, and sentences that only restate a point already made.
- Give files meaningful names. A reference to the file should tell a human what it contains.

## Technical designs

Technical designs are human integration points where people specify and discuss planned work.

- Start with a short summary of the proposed work.
- Make the early design simple enough to share and discuss.
- Use diagrams when they make structure or flow easier to understand.
- Put detailed implementation reference below the summary or in a separate document.

## Work tickets

Work tickets are human integration points where people manage planned, active, and completed work.

- Put the outcome, scope, and important constraints first.
- Use a short title that names the work in plain domain language.
- Put implementation detail below the fold or in an attached reference.
- Make acceptance criteria individually scannable.

## Pull requests

Pull requests are human integration points where people inspect ongoing work.

- Use a short title that names the work in plain domain language.
- Keep the diff as small as possible.
- Make the description digestible enough to guide review attention.
- Summarise what changed and why.
- Name the significant changes and the evidence that the work is correct.
- Avoid references to documents or code that require the reader to look something up to understand.
- Treat a description that cannot stay short as a signal to split the pull request.

## Code comments

Code comments are human integration points where people understand the intent of completed work.

- Explain intent that is not clear from the code.
- Keep comments short and close to the code they explain.
- Prefer code that makes the explanation unnecessary.
- Preserve minimum rationale needed to understand current behaviour.
- Keep change history in version control.
- Avoid distant file and identifier references that can become stale, unless they are essential to understanding the code.
- Remove comments whose information is now expressed by the code.

## Completion check

Before finishing a durable human-facing artefact, check:

- Can a human understand the important point from the top of the document?
- Can they find the section they need by scanning headings and lists?
- Does every detail earn its place, or should it move below the fold or into a separate reference?
- Does the title or file name provide a useful indicator to the nature of the content without opening the document?
