---
name: clean-mode
description: Use clean mode when creating or editing durable human-facing project artifacts, including technical designs, work tickets, pull requests, documentation, and code comments. Put important information first and make the result easy to speed-read and discuss.
---

Clean mode is the default for durable human-facing project artifacts. Write so a human can speed-read and understand the important information with minimal context.

## General principles

This document follows its own rules. Treat its shape as the target register.

### Order and language

- Put the core information at the top; move complex detail below the fold or into an attached document.
- Use simple titles and section headings that are easy to remember and discuss.
- Headings state the section's point in plain words ("Rate limits reset on every deploy"), never a metaphor or a mood ("a quiet hole", "visible pain").
- Prefer familiar language over jargon, technical terms, and code identifiers that require lookup.
- Give files meaningful names that indicate their contents.

### Structure for scanning

A reader should get the meaning by moving their eyes down the page, not by reading every line.

- Break up any paragraph that runs more than 3 sentences long.
- Use short, meaningful subtitles so a reader can find the section they need.
- Use bullet points or numbered lists for parallel items, including comma-delimited runs inside a sentence.
- Never mark structure with bold text: a multi-sentence item gets a `###` subheading, a short one gets a plain bullet.

### Say it once

- Be extremely concise. Use the fewest words that convey the important info. Sacrifice grammar for the sake of brevity.
- Cut hedging and throat-clearing ("worth noting", "this is not X, it's Y") and phrases that do not aid understanding.
- Never restate a point already made.

### Translate the source

A document inherits the register of whatever it was written from. Write in the reader's language, not the source's.

- Replace in-house nicknames and code identifiers with plain terms. If people will need the code name, map it once ('the mail queue - "the outbox" in the code') and use the plain term from then on.
- State each fact in plain words and cite its ticket or incident in parentheses; the reader must never need to open one to follow a sentence.
- Leave the source's asides, history, and hedges behind; carry over only what the reader needs.
- Explain a necessary technical term the first time it appears, in a clause, not a glossary. Terms the document is about need no explanation.

## Rewrite on sight

After drafting, re-scan the whole document and rewrite every match. These patterns survive drafting even when the principles above were followed:

- `**Label.** Sentence. Sentence.` (as a paragraph or a bullet) → a `###` subheading named `Label`, followed by the sentences. A one-sentence item folds into a plain bullet instead.
- `Columns: alpha, beta, gamma, delta, epsilon.` (four or more items delimited in one sentence) → a lead-in line, then one bullet per item. Inside a bullet, keep the bullet as the lead-in and nest one sub-bullet per item.
- "A stores its state locally. B stores its state locally. C also keeps local state." (the same kind of statement about several things in a row) → a lead-in line, then one bullet per thing.
- "The postman drains the outbox after every blue-green" (an in-house nickname or code identifier doing the work of a noun) → the plain term, mapped once at first mention if the code name aids finding it.
- A first section that explains cause, background, or mechanism (`## Problem`, `## Background`, `## Context`) with no summary above it → two or three sentences at the top stating the outcome in the reader's terms, then that section unchanged.
- A code identifier, file path, or function name in the title or the opening summary ("formatDueDate() uses local timezone instead of UTC") → the plain-language effect ("Invoice due dates show a day early for customers behind UTC"), with the identifier kept for the detail sections below.
- "What happens when Redis is down?" (a heading that asks its section's question instead of stating its answer) → the finding as a statement ("Redis being down needs a different answer per subsystem").
- Any sentence whose subject is the document itself ("This doc lays out what's firm and what isn't", "This document covers the problems and the open questions", "Below you'll find...") → delete the whole sentence. The headings already say what the document contains. This survives drafting more often than any other pattern here, so check for it explicitly.

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

- Open with what changed and why it matters, before any explanation of cause or mechanism.
- Use a short title that names the effect in plain domain language, not the function or file that changed.
- Name the significant changes and the evidence that the work is correct.
- Make the description digestible enough to guide review attention.
- Avoid references to documents or code that require the reader to look something up to understand.

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

Before finishing a durable human-facing artifact, check:

- Can a human understand the important point from the top of the document?
- Can they find the section they need by scanning headings and lists?
- Has the Rewrite on sight pass been run over the finished draft?
- Does every detail earn its place, or should it move below the fold or into a separate reference?
- Can a reader get what they need without wading through superfluous detail?
- Could a teammate who has never opened the code or the tickets follow every sentence?
- Does the title or file name provide a useful indicator to the nature of the content without opening the document?
