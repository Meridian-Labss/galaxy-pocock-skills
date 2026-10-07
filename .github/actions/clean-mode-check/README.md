# Pull requests get an advisory writing-quality comment

This action scores a pull request's description and its changed Markdown docs against the [clean-mode](../../../skills/productivity/clean-mode/SKILL.md) writing guide, then posts one comment with the scores. A low score never fails the build.

Scoring uses Jev, a judging model from TypeSafe.

## Setup

1. Add your TypeSafe API key as a repository secret named `TYPESAFE_API_KEY`.
2. Add this workflow:

```yaml
on:
  pull_request:
    # edited: re-score when the title or description changes
    types: [opened, synchronize, reopened, edited]
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
      - uses: Meridian-Labss/galaxy-pocock-skills/.github/actions/clean-mode-check@v1
        with:
          typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

Keep both permissions. Naming any permission turns off the rest, and the checkout step needs read access on private repos.

## Settings

| Input | Default | Effect |
|---|---|---|
| `typesafe-api-key` | none | Without a key, the check skips. |
| `github-token` | the workflow's token | Used to post the comment. |
| `include` | `**/*.md` | Which files to score, as comma-separated patterns. Case-sensitive; `*` also matches inside subfolders. Add `**/*.mdx` to opt in (untested). |
| `max-files` | `10` | Most docs to score. The most-changed docs go first. |
| `max-chars` | `75000` | Longer docs are skipped, not cut short. Keeps each doc within Jev's size limit. |
| `min-lines` | `3` | Docs with smaller changes are skipped. |

## Limits

- Each file is scored as a whole, so old text affects the score.
- Pull requests from forks are not scored, because GitHub withholds secrets from them.
- Runs only for pull request events. Other triggers log a notice and stop. Use the `pull_request` trigger shown above, not `pull_request_target`, which would expose secrets to untrusted code.
- Needs the full git history (the `fetch-depth: 0` line above). Without it, the step fails and says so.
- Linux and macOS runners only. Check the repo out to the default folder.
- The comment lists at most 20 skipped files.

## Releasing

Other repos pin the `v1` tag. After a release, move it:

```bash
git tag -f v1 && git push -f origin v1
```
