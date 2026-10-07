# Clean-mode CI check: design

A GitHub Action that scores the prose in a pull request against clean-mode and posts the results as one PR comment. Advisory: weak prose or an outage at Jev or GitHub never fails the build.

Any repo can use it by adding the action and a TypeSafe API key. Scoring uses Jev (TypeSafe's judging model) with the clean-mode eval rubrics that judge a document on its own.

## Scope

In scope:

- Changed Markdown files, each judged as a whole document
- The PR title and body, judged together as one document

Out of scope, planned as a separate project: code comments. The current rubrics were only tested on whole documents, so comments need their own rubrics and test fixtures first.

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
| `max-files` | `10` | Docs ranked by lines changed (additions plus deletions); the rest are listed as "not scored" |
| `max-chars` | `30000` | Larger files are skipped with a note, not truncated, since a cut-off document scores badly for the wrong reason |
| `min-lines` | `3` | Docs with fewer lines changed (typo fixes) are not scored |

No outputs. Results go to the PR comment and the job summary page.

### Versioning

`v1` is a git tag moved by hand when a release of the action should reach consumers. The changesets release workflow does not manage it. Dependencies are pinned in `evals/requirements.txt`, which the action installs.

## Components

| File | Job |
|---|---|
| `.github/actions/clean-mode-check/action.yml` | Set up Python, install deps, run the CLI, post the comment |
| `ci/clean_mode_check.py` | CLI: collect changed prose, score it, render a Markdown summary |
| `evals/jev_core.py` | New shared module: load `dimensions.json`, build Jev questions, call Jev, normalize scores, compute composites |
| `evals/dimensions.json` | Unchanged. The single source of rubrics for evals and CI |

The action runs these files from its own checkout (`${{ github.action_path }}/../../..`), never from the consumer's repo.

### Shared scoring module

`evals/score_with_jev.py` is refactored to import `jev_core.py`, so evals and CI ask Jev identical questions. To be importable and testable, `jev_core`:

- raises exceptions instead of calling `sys.exit`; each CLI turns them into exits
- takes the Jev client as a parameter, so tests can pass a fake
- takes a filter for which rubric groups to ask, so CI asks only the rubrics that need no source document

### Local use

The CLI prints the same summary locally:

```
python ci/clean_mode_check.py --base main --pr-title "..." --pr-body-file body.md
```

## What happens on each PR

1. Collect changed docs: `git diff --numstat` from `github.event.pull_request.base.sha` to head. Include added, modified, and renamed-with-edits files matching `include`.
2. Build the PR item as `# {title}\n\n{body}`. If the body is empty, report "no description" and skip it.
3. Score each item with one Jev call over its full text.
4. Render a summary per item (format below).
5. Post one comment, found and updated on later pushes by a hidden `<!-- clean-mode-check -->` marker. Also write the summary to the job summary page.

About 11 Jev calls per push at most: 10 docs plus the PR item.

### Which rubrics apply

Some rubrics compare a document against the prompt it was written from. CI has no such prompt, so it skips them. The rest:

- `core_info_first`
- `title_names_the_outcome`
- `scannability` (mean of `blocks_kept_short`, `parallel_items_listed`, `heading_clarity`)
- `structure_not_bolded`
- `plain_language`
- `concision` (mean of `padding`, `economy`)

Each rubric's score is normalized to 0 to 1 by its top level. An item's overall score is the unweighted mean of these six.

### Comment format

One table, one row per item, lowest score first:

- overall score
- the up to 3 weakest single rubrics below full marks, with scores (composites expanded into their parts; ties broken by order in `dimensions.json`)

Below it, a collapsed block explains the weak rubrics. Each rubric level Jev chose appears once, followed by the items it applies to.

The comment links to clean-mode's `SKILL.md` and states that scores cover the whole file, not just the PR's changes.

## Failure handling

- No API key (normal for PRs from forks): log a notice, post nothing, exit 0.
- A Jev call fails: no retry. Mark that item "could not score" and continue.
- Posting the comment fails: the job summary still has the results. Warn and exit 0.
- Bad `dimensions.json` or a crash in the CLI: exit non-zero. These are bugs in the tool and should be visible.

## Security

The `pull_request` trigger is used, not `pull_request_target`, so code from a PR never runs with secrets. As a result, PRs from forks are not scored.

## Testing

- CLI unit tests: pytest with a fake Jev client. Cover:
  - collection: include filter, `min-lines`, size and file caps, deletions ignored, renames with edits included
  - rendering: composites expanded, weakest chosen and tie-broken correctly, level text shown, "not scored", "could not score" and "no description" rows, marker present
  - failures: a failed Jev call affects only its item and the run exits 0; a missing key exits 0 without posting
  - comment: update when the marker exists, create otherwise (GitHub API stubbed)
- End to end: a throwaway PR in this repo using the action locally (`uses: ./.github/actions/clean-mode-check`), adding one padded doc and one clean doc. Check that one comment appears, a second push updates it, and the padded doc scores lower.
- New `.github/workflows/test.yml` runs pytest on PRs touching `ci/`, `evals/jev_core.py`, `evals/score_with_jev.py`, `evals/dimensions.json`, or `.github/actions/`.
