# Clean-mode check

Scores a pull request's description and changed Markdown docs against [clean-mode](../../../skills/productivity/clean-mode/SKILL.md) with Jev (TypeSafe's judging model), then posts one advisory comment. It never fails the build on a low score.

## Usage

Add a `TYPESAFE_API_KEY` Actions secret, then:

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
      - uses: Meridian-Labss/galaxy-pocock-skills/.github/actions/clean-mode-check@v1
        with:
          typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

Keep `contents: read`: listing any permission sets the rest to none, and checkout needs it on private repos.

## Inputs

| Input | Default | Behavior |
|---|---|---|
| `typesafe-api-key` | none | TypeSafe API key. If empty, the check skips. |
| `github-token` | `${{ github.token }}` | Posts the comment. |
| `include` | `**/*.md` | Comma-separated globs of files to score. Case-sensitive; `*` also matches across `/`. Add `**/*.mdx` to opt in (rubrics are untested on MDX). |
| `max-files` | `10` | Most docs to score, ranked by lines changed. |
| `max-chars` | `75000` | Longer docs are skipped, not truncated. The default keeps each doc inside Jev's 32k-token limit. |
| `min-lines` | `3` | Docs with fewer lines changed are not scored. |

## Limits

- Scores cover whole files, not just the PR's changes.
- The "Not scored" list shows at most 20 entries.
- Linux and macOS runners only.
- Check out to the workspace root (no `path:` on `actions/checkout`).
- Fork PRs are not scored: no secrets reach them.
- Runs on `pull_request` events only (not `pull_request_target`). On any other trigger it logs a notice and does nothing.
- Needs `fetch-depth: 0`. If the base commit is missing (shallow checkout), the step fails with an error naming it.
- The diff runs against the PR's head commit.

## Releasing

Consumers pin `@v1`. After a release, move the tag:

```bash
git tag -f v1 && git push -f origin v1
```
