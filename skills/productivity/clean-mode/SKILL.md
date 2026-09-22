---
name: clean-mode
description: Use clean mode when creating or editing durable human-facing project artefacts, including technical designs, work tickets, pull requests, documentation, and code comments. Put important information first and make the result easy to speed-read and discuss.
---

Clean mode is the default for durable human-facing project artefacts. Write so a human can speed-read and understand the important information with minimal context.

## General principles

- Put the core information at the top. Move complex detail below the fold or into an attached document.
- Use meaningful titles and simple section headings that are easy to remember and discuss.
- Prefer familiar language over jargon, technical terms, and code identifiers that require lookup.
- Use short paragraphs and meaningful subtitles.
- Use bullet points or numbered lists for parallel items.
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
- Use a short title that names the work in domain language.
- Put implementation detail below the fold or in an attached reference.
- Make acceptance criteria individually scannable.

## Pull requests

Pull requests are human integration points where people inspect ongoing work.

- Keep the diff as small as possible.
- Make the description digestible enough to guide review attention.
- Summarise what changed, not how it was implemented.
- Name the significant changes and the evidence that the work is correct.
- Treat a description that cannot stay short as a signal to split the pull request.

## Code comments

Code comments are human integration points where people understand the intent of completed work.

- Explain intent that is not clear from the code.
- Keep comments short and close to the code they explain.
- Prefer code that makes the explanation unnecessary.
- Do not use comments as decision logs or records of recent changes.
- Avoid distant file and identifier references that can become stale.
- Remove comments whose information is now expressed by the code.

## Completion check

Before finishing a durable human-facing artefact, check:

- Can a human understand the important point from the top of the document?
- Can they find the section they need by scanning headings and lists?
- Does every detail earn its place, or should it move below the fold or into a separate reference?
- Is the title or file name meaningful without opening the document?
