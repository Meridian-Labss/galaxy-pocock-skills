# Pull requests get an advisory writing-quality comment

A GitHub Action scores the prose in each pull request against the clean-mode writing guidelines and posts the results as one comment on the pull request. Advisory only: weak prose, or an outage at Jev or GitHub, never fails the build.

Any repo can use it by adding the action and a TypeSafe API key. Jev (TypeSafe's judging model) does the scoring, using only the clean-mode rubrics that judge a document without the prompt it was written from.

## Scope

In scope:

- Changed Markdown files, each judged as a whole document
- The pull request's title and description, judged together as one document

Out of scope, planned as a separate project: code comments. The current rubrics were only tested on whole documents, so comments need their own rubrics and test cases first.

## How a repo uses it

```yaml
on: pull_request
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: clean-mode-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  clean-mode:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: <org>/galaxy-pocock-skills/.github/actions/clean-mode-check@v1
        with:
          typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

### Inputs

| Input | Default | Behavior |
|---|---|---|
| `typesafe-api-key` | none | Exported as `TYPESAFE_API_KEY`. If empty, the check skips (see Failure handling) |
| `github-token` | `${{ github.token }}` | Used to post the comment |
| `include` | `**/*.md` | Comma-separated globs of files to score. Add `**/*.mdx` to opt in; rubrics are untested on MDX |
| `max-files` | `10` | Most docs scored, largest change first (lines added plus deleted); the rest are listed as "not scored" |
| `max-chars` | `75000` | Larger files are skipped with a note, not truncated, since a cut-off document scores badly for the wrong reason. Sized to Jev's 32k-token limit on the document plus its longest question, at a worst case of 2.5 characters per token |
| `min-lines` | `3` | Docs with fewer lines changed (typo fixes) are not scored |

No outputs. Results go to the pull request comment and the job summary page.

### Versioning

Consumers pin to `v1`, a git tag moved by hand when a release should reach them. This repo's automated release process does not move it.

## Components

| File | Job |
|---|---|
| `.github/actions/clean-mode-check/action.yml` | Set up Python, install dependencies, run the command-line tool, post the comment |
| `ci/clean_mode_check.py` | Command-line tool: collect changed prose, score it, render a Markdown summary |
| `evals/jev_core.py` | New shared scoring module: load the rubrics, build Jev questions, call Jev, normalize scores, compute combined rubrics |
| `evals/dimensions.json` | Unchanged. The single source of rubrics for evals and the check |

The action runs these files from its own copy of this repo, never from the consumer's repo, and installs dependencies pinned in `evals/requirements.txt`.

### Shared scoring module

The eval scoring script now uses the shared scoring module (`evals/jev_core.py`), so evals and the check ask Jev identical questions. To be importable and testable, the shared module:

- raises errors instead of exiting the program; each command-line tool turns them into exits
- takes the Jev client as a parameter, so tests can pass a fake
- takes a list of rubrics to ask, so the check can leave out those that need the prompt a document was written from

### Local use

The command-line tool prints the same summary locally:

```
python ci/clean_mode_check.py --base main --pr-title "..." --pr-body-file body.md
```

## What happens on each pull request

1. Collect changed docs: every file added, modified, or renamed with edits since the branch split from the pull request's base commit, matching `include`.
2. Join the title and description into one document. If the description is empty, report "no description" and skip it.
3. Score each item with one Jev call over its full text.
4. Render a summary per item (format below).
5. Post one comment, found and updated on later pushes by a hidden marker. Also write the summary to the job summary page.

At most 11 Jev calls per push with default settings: 10 docs plus the title and description.

### Which rubrics apply

The check skips rubrics that compare a document against the prompt it was written from, since it has no such prompt. The rest:

- Important point first (`core_info_first`)
- Title names the outcome (`title_names_the_outcome`)
- Easy to scan (`scannability`): mean of `blocks_kept_short`, `parallel_items_listed`, `heading_clarity`
- No bold as structure (`structure_not_bolded`)
- Plain language (`plain_language`)
- Concise (`concision`): mean of `padding`, `economy`

Each score is scaled to 0 to 1 by dividing by the rubric's highest level. An item's overall score is the unweighted mean of these six.

### Comment format

One table, one row per item, lowest score first, showing:

- overall score
- up to 3 weakest single rubrics below full marks, with scores. Combined rubrics are split into their parts; ties go to the rubric listed first in `evals/dimensions.json`.

Below the table, a collapsed block explains the weak rubrics. Each level description Jev picked appears once, followed by the items it applies to.

The comment links to clean-mode's `SKILL.md` and states that scores cover the whole file, not just the pull request's changes.

## Failure handling

- No API key (normal for pull requests from forks): log a notice, post nothing, exit 0.
- A Jev call fails: no retry. Mark that item "could not score" and continue.
- Posting the comment fails: the job summary still has the results. Warn and exit 0.
- A broken rubric file or a crash in the tool: exit non-zero. These are bugs in the tool and should be visible.

## Security

The action runs on the `pull_request` trigger, not `pull_request_target`, so code from a pull request never runs with secrets. As a result, pull requests from forks are not scored.

## Testing

- Unit tests (pytest, fake Jev client) cover:
  - collection: include filter, minimum lines changed, size and file caps, deletions ignored, renames with edits included
  - rendering: combined rubrics split, weakest chosen and ties broken correctly, level text shown, "not scored", "could not score" and "no description" rows, marker present
  - failures: a failed Jev call affects only its item and the run exits 0; a missing key exits 0 without posting
  - comment: update when the marker exists, create otherwise (GitHub API stubbed)
- End to end: a throwaway pull request in this repo, running the action from the local checkout (`uses: ./.github/actions/clean-mode-check`) and adding one padded doc and one clean doc. Check that one comment appears, a second push updates it, and the padded doc scores lower.
- New `.github/workflows/test.yml` runs the unit tests on pull requests touching `ci/`, `evals/jev_core.py`, `evals/score_with_jev.py`, `evals/dimensions.json`, or `.github/actions/`.
