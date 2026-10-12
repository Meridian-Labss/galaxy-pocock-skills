# The writing check can use OpenAI's judge as well as TypeSafe's

The clean-mode evals and the pull request check both send writing to a judging model and get rubric scores back. Today that judge is always TypeSafe's Jev. This change puts the judge behind a small interface and adds a second one, OpenAI's Decisions API, so the two can be compared on the same outputs and either used in CI.

TypeSafe stays the default. Nothing changes for current users unless they choose OpenAI.

## Choosing a judge

| Where | Setting | Default |
|---|---|---|
| Eval scorer | `--judge typesafe` or `--judge openai` | `typesafe` |
| Pull request check command | `--judge typesafe` or `--judge openai` | `typesafe` |
| GitHub Action | `judge` input, plus a new `openai-api-key` input | `typesafe` |

- Each judge reads its own key: `TYPESAFE_API_KEY` or `OPENAI_API_KEY`.
- The check's "no key, skipping" notice names the key the chosen judge needs.
- Eval reports print the judge and model in their header. Result folders end in `-<judge>` instead of `-jev`.

## Comparing the judges

One judge per run. To compare on identical outputs, re-score a saved report with the other judge:

```
python evals/score_evals.py --from-report evals/results/<run>/report.md --judge openai
```

No side-by-side table yet; add one if the judges get switched often.

## One interface, one adapter per provider

The shared scoring module asks a judge one thing: score this text against these rubrics. An adapter (the code that translates for one provider) keeps each provider's request and answer shapes to itself.

```
evals/
  scoring.py          renamed from jev_core.py: load rubrics, ask a judge, add combined rubrics
  judges/
    __init__.py       the Judge interface, JudgeError, make_judge(name)
    typesafe.py       adapter for TypeSafe's Jev (today's behavior, moved)
    openai.py         adapter for OpenAI's Decisions API
```

### The interface

```python
class Judge(Protocol):
    name: str                         # "typesafe" or "openai"
    model: str                        # for report headers
    def score(self, text: str, rubrics: dict[str, Rubric]) -> dict[str, Answer]: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Judge": ...
    def __exit__(self, *exc) -> None: ...   # calls close()

@dataclass(frozen=True)
class Rubric:
    instructions: str
    levels: list[str]                 # worst to best: the rubric file's `criteria`

@dataclass(frozen=True)
class Answer:
    score: float                      # expected level, 0 to len(levels) - 1
    confidence: float
    probabilities: dict[int, float]   # level -> probability
```

- `make_judge(name, retries=None)` returns a judge.
  - An unknown name fails with the list of valid ones.
  - `retries=0` turns off the provider's own retries, as the pull request check requires. `None` keeps the provider's default (the evals use this).
- Any provider-side failure raises `JudgeError`: network errors, rate limits, refusals, an answer missing for any rubric. Both adapters behave the same way.
- Each adapter imports its provider's library only when chosen.

### What stays the same in scoring

- `scoring.score_text` still groups rubrics by their input layout, fills each layout with the document (and the source, for rubrics that compare against it), and makes one call per group: `judge.score(filled_layout, rubrics_in_group)`.
- It still stringifies probability keys and adds combined rubrics, so reports and saved `scores.json` files are unaffected.

### The OpenAI adapter

Checked against `openai` 3.29.0, which has `client.decisions.create`.

- Model: `gpt-6-luna`, the model OpenAI's Decisions guide names, kept as a constant in the adapter.
- Each rubric becomes a `score` question, always with its `name` set: `{"type": "score", "name": …, "instructions": …, "levels": [{"label": "level 0", "description": <criterion text>}, …]}`.
- All rubrics in a group go in one request, with the filled layout as `input`.
- Answers come back as a list and are matched by `name`. `score` and `confidence` map directly; `probabilities` (a list of `value`, `label`, `probability`) becomes `{value: probability}`.
- A refusal or a missing answer raises `JudgeError`, so an item is never half scored.
- `openai.OpenAIError` becomes `JudgeError`. `retries=0` becomes `OpenAI(max_retries=0)`.
- OpenAI publishes no token limit for this API. The 75,000-character cap stays; an oversized document fails as "could not score".

## What changes elsewhere

### Renames

Names that are no longer specific to Jev change in the same pass:

| Old | New |
|---|---|
| `evals/jev_core.py` | `evals/scoring.py` |
| `evals/score_with_jev.py` | `evals/score_evals.py` |
| `evals/run_jev.sh` | `evals/run_evals.sh` |
| `package.json` script `eval:clean-mode:jev` | `eval:clean-mode:score` |
| `tests/fake_jev.py` | `tests/fake_judge.py` |
| `tests/test_jev_core.py` | `tests/test_scoring.py` |
| Report title "Clean-mode Jev scoring report", "Jev report:" printout | "Clean-mode scoring report", "Report:" |

### Eval scorer

- `--judge`, passed to `make_judge`.
- `run_evals.sh` stops checking for `TYPESAFE_API_KEY` and lets the scorer report a missing key for the chosen judge.
- A `JudgeError` still ends the run, as a judge failure does today: an eval report with gaps is not worth comparing.

### Pull request check command

- `--judge`, passed to `make_judge(name, retries=0)`.
- `main(client=…)` becomes `main(judge=…)` for tests.
- `ci/clean_mode_check.py` and `ci/render.py` import `scoring` instead of `jev_core`.
- Catches `JudgeError` instead of `TypeSafeError`. The warning says "could not score" without naming Jev.
- The comment on the 75,000-character cap explains it in terms of TypeSafe's limit and notes that OpenAI publishes none.

### GitHub Action

- New inputs: `judge` (default `typesafe`) and `openai-api-key`.
- The step passes `--judge "$JUDGE"` and sets `OPENAI_API_KEY` from the new input.
- `action.yml` description and the README name both judges:
  - the opening line and setup step 1 (which key to add)
  - the settings table (two new rows)
  - the "Jev's size limit" wording in the `max-chars` row and anywhere else Jev is named
- Both libraries are installed on every run, on purpose: one requirements file is simpler than per-judge installs, and the extra install time is small.

### Dependencies and test workflow

- `evals/requirements.txt` adds `openai==3.29.0`, pinned.
- `.github/workflows/test.yml` path filters change `evals/jev_core.py` to `evals/scoring.py` and `evals/judges/**`, and `evals/score_with_jev.py` to `evals/score_evals.py`.

## Testing

No network calls and no real provider requests in tests.

### Existing tests that move

- The fake judge implements the interface directly. It records `{"text", "rubrics"}` per call and raises `JudgeError`.
- Assertions on `client.calls[…]["state"]` in `tests/test_cli.py` become `["text"]`.
- `tests/test_render.py` and `tests/test_cli.py` switch to `scoring` and the fake judge.
- The retry test in `test_jev_core.py` moves to the TypeSafe adapter's tests.

### New tests

- TypeSafe adapter, against a stand-in client returning TypeSafe's response shape:
  - request built correctly
  - answers mapped to `Answer`
  - a missing answer raises `JudgeError`
  - `TypeSafeError` becomes `JudgeError`
  - `retries=0` turns retries off
- OpenAI adapter, against a stand-in `decisions.create` returning the library's real response types:
  - each rubric sent as a `score` question with `name` set and labeled levels
  - answers matched by `name`, even out of order
  - refusal or missing answer raises `JudgeError`
  - `OpenAIError` becomes `JudgeError`
  - `retries=0` reaches the client
- `make_judge`: both names work; an unknown name lists the valid ones.
- Check command: `--judge openai` makes the missing-key notice name `OPENAI_API_KEY`.

### Live check

With the user's approval first: re-score one existing eval report with each judge to confirm OpenAI works end to end.

## Rollout

- Built on branch `feat/swappable-judge`, from the pull request check branch (pull request #4).
- It lands in pull request #4 or right after it.
- Afterwards, the code comment check's plan is updated to the new names before it runs:
  - the plan is `docs/superpowers/plans/2026-10-07-clean-mode-comment-check.md` on branch `feat/clean-mode-comment-check`
  - a reviewer checks that every code block in it fits the new interface
