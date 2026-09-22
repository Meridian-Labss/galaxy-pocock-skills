## What it does

`clean-mode` is the writing standard for durable human-facing project artefacts. It makes technical designs, work tickets, pull requests, documentation, and code comments easy to speed-read and discuss with minimal context.

Its defining constraint is that the important information must be understandable from the top of the artefact. Detail still belongs in the project, but it moves below the fold or into a separate reference when it would slow the first read.

## When to reach for it

Type `/clean-mode`, or the agent reaches for it automatically when a task creates or edits a durable human-facing artefact.

Reach for it when writing a technical design, ticket, pull request, project document, or code comment. It is a default writing standard, not a format-specific template.

## The four integration points

- **Technical designs:** start with a short summary and keep the early design easy to discuss. Use diagrams when they clarify structure or flow.
- **Work tickets:** put the outcome, scope, constraints, and acceptance criteria first. Keep implementer detail below the fold.
- **Pull requests:** keep the diff small and the description digestible. Summarise what changed, name significant changes, and show evidence.
- **Code comments:** explain local intent that the code cannot express. Keep comments short, avoid decision logs and change history, and remove stale explanations.

## Common questions

**Does clean mode apply to agent narration?**

No. It applies to durable project artefacts. Conversation can remain conversational; the project record should remain easy for humans to inspect later.

**Does clean mode mean every document must be short?**

No. It means the important information is easy to find first. Detailed material can follow or live in a linked document.

## It's working if

- A human can explain the document's purpose after reading only its opening section.
- Headings, lists, and short paragraphs reveal the structure without a close read.
- Technical detail is available without obscuring the decision, outcome, or intent.
- Code comments explain why the code is shaped this way without repeating the code or recording stale history.

## Where it fits

This is a model-invoked writing standard used by the technical-design, ticket, implementation, and review flows. Use [writing-for-agents](https://aihero.dev/skills-writing-for-agents) for documents whose primary reader is an agent; use clean mode when humans need to inspect the durable artefact. [ask-matt](https://aihero.dev/skills-ask-matt) routes the broader workflow.
