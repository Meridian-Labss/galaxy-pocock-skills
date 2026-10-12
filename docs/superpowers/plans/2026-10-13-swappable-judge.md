# Swappable Judge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The clean-mode eval scorer and the pull request check can score writing with either TypeSafe's Jev (the default) or OpenAI's Decisions API.

**Architecture:**

- A new `evals/judges/` package defines one small interface: score this text against these rubrics. One adapter per provider (TypeSafe, OpenAI) translates to and from that provider's request and answer shapes.
- The shared scoring module (renamed from `jev_core.py` to `scoring.py`) asks a judge instead of calling the TypeSafe client.
- The eval scorer and the check command each gain `--judge`; the GitHub Action gains `judge` and `openai-api-key` inputs.

**Tech Stack:** Python 3.12 in CI (3.14 locally), TypeSafe SDK 0.7.2, OpenAI Python library 3.29.0, pytest, GitHub composite actions.

**Spec:** [docs/superpowers/specs/2026-10-13-swappable-judge-design.md](../specs/2026-10-13-swappable-judge-design.md)

---

## Before you start

- Branch: stay on `feat/swappable-judge`. Do not switch branches.
- Python: `evals/.venv/bin/python`. Task 1 adds the OpenAI library to it.
- Run tests with both API keys unset, so no test can reach a provider:
  `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
  45 tests pass before Task 1.
- Repo rules:
  - no em-dashes in prose, comments, or commit messages
  - American spelling in new text
  - run the `clean-mode` skill before editing the action README (Task 8)
  - stage files by name; never `git add -A` or `git add .`
  - end every commit message with a blank line, then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command below does this)
- How the two providers behave:
  - TypeSafe: `TypeSafeClient().system_one(state=..., questions={name: Score(...)})` returns answers keyed by name. Every SDK error, including a missing key at construction, is a `TypeSafeError`. Its default model is `jev-latest`, or `TYPESAFE_DEFAULT_MODEL` when set.
  - OpenAI: `OpenAI().decisions.create(model=..., input=..., questions=[...])` returns a `Decision` whose `answers` is a list, each with a `name` and a `type` of `score` or `refusal`. Every library error, including a missing key at construction, is an `OpenAIError`. `OpenAI(max_retries=0)` turns retries off.

## File map

| File | Responsibility |
|---|---|
| `evals/requirements.txt` | Modify. Pin `openai==3.29.0` |
| `evals/jev_core.py` → `evals/scoring.py` | Rename, then modify. Load rubrics, ask a judge, add combined rubrics |
| `evals/score_with_jev.py` → `evals/score_evals.py` | Rename, then modify. Eval scorer: `--judge`, judge in the report header and folder name |
| `evals/run_jev.sh` → `evals/run_evals.sh` | Rename, then modify. Stop checking for `TYPESAFE_API_KEY` |
| `evals/judges/__init__.py` | Create. `Judge` interface, `Rubric`, `Answer`, `JudgeError`, `API_KEY_ENV`, `make_judge` |
| `evals/judges/typesafe.py` | Create. TypeSafe adapter |
| `evals/judges/openai.py` | Create. OpenAI adapter |
| `ci/clean_mode_check.py` | Modify. `--judge`, `main(judge=...)`, catch `JudgeError` |
| `ci/render.py` | Modify. Import `scoring`; drop "Jev" from docstrings |
| `tests/fake_jev.py` → `tests/fake_judge.py` | Rename, then rewrite as a fake judge |
| `tests/test_jev_core.py` → `tests/test_scoring.py` | Rename, then modify |
| `tests/test_cli.py`, `tests/test_render.py` | Modify. Use the fake judge |
| `tests/test_judges.py`, `tests/test_typesafe_judge.py`, `tests/test_openai_judge.py`, `tests/test_score_evals.py` | Create |
| `package.json` | Modify. Script `eval:clean-mode:jev` → `eval:clean-mode:score` |
| `.github/workflows/test.yml` | Modify. Path filters follow the renames |
| `.github/actions/clean-mode-check/action.yml`, `README.md` | Modify. `judge` and `openai-api-key` inputs |

The top-level `README.md` names none of the renamed files, so it does not change.

---

## Chunk 1: Dependency and renames

### Task 1: Add the OpenAI library

**Files:**
- Modify: `evals/requirements.txt`

- [ ] **Step 1: Pin the library**

`evals/requirements.txt` becomes:

```
typesafe-sdk==0.7.2
openai==3.29.0
pyyaml==6.0.3
```

- [ ] **Step 2: Install it**

Run: `evals/.venv/bin/pip install -q -r evals/requirements-dev.txt && evals/.venv/bin/python -c "import openai, typesafe_sdk; print(openai.__version__, typesafe_sdk.__version__)"`
Expected: `3.29.0 0.7.2`

- [ ] **Step 3: Confirm nothing broke**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `45 passed`

- [ ] **Step 4: Commit**

```bash
git add evals/requirements.txt
git commit -m "Pin openai 3.29.0 for the OpenAI judge" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Rename the Jev-specific files

Renames only, plus the import and label edits that keep tests green. No behavior changes. `git mv` keeps each file's history.

**Files:**
- Rename: `evals/jev_core.py` → `evals/scoring.py`, `evals/score_with_jev.py` → `evals/score_evals.py`, `evals/run_jev.sh` → `evals/run_evals.sh`, `tests/fake_jev.py` → `tests/fake_judge.py`, `tests/test_jev_core.py` → `tests/test_scoring.py`
- Modify: `ci/clean_mode_check.py`, `ci/render.py`, `tests/test_cli.py`, `tests/test_render.py`, `package.json`, `.github/workflows/test.yml`

- [ ] **Step 1: Move the files**

```bash
git mv evals/jev_core.py evals/scoring.py
git mv evals/score_with_jev.py evals/score_evals.py
git mv evals/run_jev.sh evals/run_evals.sh
git mv tests/fake_jev.py tests/fake_judge.py
git mv tests/test_jev_core.py tests/test_scoring.py
```

- [ ] **Step 2: Watch the tests fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `3 errors` during collection, each `No module named 'jev_core'`

- [ ] **Step 3: Update the module names everywhere they are used**

```bash
perl -pi -e 's/\bjev_core\b/scoring/g; s/\bfake_jev\b/fake_judge/g; s/\bscore_with_jev\.py\b/score_evals.py/g' \
  ci/clean_mode_check.py ci/render.py evals/score_evals.py evals/run_evals.sh \
  tests/test_cli.py tests/test_render.py tests/test_scoring.py .github/workflows/test.yml
```

This covers the imports, `run_evals.sh`'s `exec` line, the scorer's docstring usage line, and the two path filters in `test.yml` (which become `evals/scoring.py` and `evals/score_evals.py`).

- [ ] **Step 4: Rename the report labels and the npm script**

In `evals/score_evals.py`:
- `"# Clean-mode Jev scoring report",` → `"# Clean-mode scoring report",`
- `print(f"Jev report: {report_path}")` → `print(f"Report: {report_path}")`

In `package.json`:
- `"eval:clean-mode:jev": "evals/run_jev.sh"` → `"eval:clean-mode:score": "evals/run_evals.sh"`

- [ ] **Step 5: Run the tests and a smoke check**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q && evals/.venv/bin/python evals/score_evals.py --help | head -1`
Expected: `45 passed`, then `usage: score_evals.py ...`

Run: `git grep -n "jev_core\|fake_jev\|score_with_jev\|run_jev\|clean-mode:jev\|Jev scoring report\|Jev report" -- ':!docs'`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add evals/scoring.py evals/score_evals.py evals/run_evals.sh tests/fake_judge.py tests/test_scoring.py \
  ci/clean_mode_check.py ci/render.py tests/test_cli.py tests/test_render.py package.json .github/workflows/test.yml
git status --short | grep -v '^??'   # expect five R lines and six M lines, all staged
git commit -m "Rename the Jev-specific eval and scoring files to judge-neutral names" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Chunk 2: The judge interface

### Task 3: Judge interface and TypeSafe adapter

Additive: nothing uses the new package yet.

**Files:**
- Create: `evals/judges/__init__.py`, `evals/judges/typesafe.py`
- Create: `tests/test_judges.py`, `tests/test_typesafe_judge.py`
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: Write the failing tests**

`tests/test_judges.py`:

```python
import pytest

import judges


def test_make_judge_builds_the_typesafe_judge(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    with judges.make_judge("typesafe") as judge:
        assert judge.name == "typesafe"


def test_unknown_judge_lists_the_valid_ones():
    with pytest.raises(ValueError, match="typesafe, openai"):
        judges.make_judge("gemini")


def test_each_judge_names_its_key():
    assert judges.API_KEY_ENV == {"typesafe": "TYPESAFE_API_KEY", "openai": "OPENAI_API_KEY"}
```

`tests/test_typesafe_judge.py` builds real `SystemOneResponse` objects. The SDK validates strictly, so build them from JSON (`model_validate_json`), the way the SDK parses a live reply; `model_validate` on a dict rejects the string level keys.

```python
import json

import pytest
from typesafe_sdk import SystemOneResponse, TypeSafeError

from judges import Answer, JudgeError, Rubric
from judges import typesafe as typesafe_judge

RUBRICS = {
    "padding": Rubric(instructions="Is it padded?", levels=["very", "a little", "not at all"]),
    "economy": Rubric(instructions="Is it economical?", levels=["no", "yes"]),
}


def response(answers):
    """A real SystemOneResponse, parsed from the JSON TypeSafe sends back."""
    return SystemOneResponse.model_validate_json(json.dumps({
        "model": "jev-latest",
        "usage": {"input_tokens": 10, "output_tokens": 2},
        "answers": answers,
    }))


def score_answer(score, probabilities):
    return {
        "type": "score", "score": score, "confidence": 0.8,
        "legend": {k: f"level {k}" for k in probabilities},
        "probabilities": probabilities,
    }


class StandInClient:
    """Records system_one calls and returns a canned response or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.closed = False

    def system_one(self, state, questions):
        self.calls.append({"state": state, "questions": questions})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self):
        self.closed = True


def both_answered():
    return response({
        "padding": score_answer(1.5, {"0": 0.1, "1": 0.3, "2": 0.6}),
        "economy": score_answer(0.9, {"0": 0.1, "1": 0.9}),
    })


def test_sends_each_rubric_as_a_score_question_with_the_text_as_state():
    client = StandInClient(both_answered())
    typesafe_judge.TypeSafeJudge(client=client).score("the doc", RUBRICS)
    (call,) = client.calls
    assert call["state"] == "the doc"
    assert set(call["questions"]) == {"padding", "economy"}
    padding = call["questions"]["padding"]
    assert padding.type == "score"
    assert padding.instructions == "Is it padded?"
    assert list(padding.criteria) == ["very", "a little", "not at all"]


def test_maps_answers_to_judge_answers():
    answers = typesafe_judge.TypeSafeJudge(client=StandInClient(both_answered())).score("doc", RUBRICS)
    assert answers["padding"] == Answer(score=1.5, confidence=0.8, probabilities={0: 0.1, 1: 0.3, 2: 0.6})
    assert answers["economy"].probabilities == {0: 0.1, 1: 0.9}


def test_a_missing_answer_raises_judge_error():
    partial = response({"padding": score_answer(1.0, {"0": 0.5, "1": 0.5})})
    with pytest.raises(JudgeError, match="economy"):
        typesafe_judge.TypeSafeJudge(client=StandInClient(partial)).score("doc", RUBRICS)


def test_typesafe_errors_become_judge_errors():
    client = StandInClient(TypeSafeError("rate limited"))
    with pytest.raises(JudgeError, match="rate limited"):
        typesafe_judge.TypeSafeJudge(client=client).score("doc", RUBRICS)


def test_retries_zero_turns_retries_off(monkeypatch):
    seen = {}
    monkeypatch.setattr(typesafe_judge, "TypeSafeClient", lambda **kwargs: seen.update(kwargs))
    typesafe_judge.TypeSafeJudge(retries=0)
    assert seen["retry"].max_retries == 0


def test_default_retries_leave_the_client_default(monkeypatch):
    seen = {}
    monkeypatch.setattr(typesafe_judge, "TypeSafeClient", lambda **kwargs: seen.update(kwargs))
    typesafe_judge.TypeSafeJudge()
    assert seen == {}


def test_a_missing_key_raises_judge_error_naming_it(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JudgeError, match="TYPESAFE_API_KEY"):
        typesafe_judge.TypeSafeJudge()


def test_closing_the_judge_closes_the_client(monkeypatch):
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    client = StandInClient(both_answered())
    with typesafe_judge.TypeSafeJudge(client=client) as judge:
        assert judge.name == "typesafe"
        assert judge.model == "jev-latest"
    assert client.closed
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_judges.py tests/test_typesafe_judge.py`
Expected: 2 collection errors, `ModuleNotFoundError: No module named 'judges'`

- [ ] **Step 3: Write `evals/judges/__init__.py`**

```python
"""The judging models the scorer can ask, behind one small interface.

A judge scores one text against a set of rubrics. Each provider has an
adapter in this package that keeps its request and answer shapes to itself,
and imports its provider's library only when chosen.
"""
from dataclasses import dataclass
from typing import Protocol

# Each judge reads its own API key from this environment variable.
API_KEY_ENV = {"typesafe": "TYPESAFE_API_KEY", "openai": "OPENAI_API_KEY"}
NAMES = tuple(API_KEY_ENV)


class JudgeError(Exception):
    """The provider failed: network error, rate limit, refusal, or a missing answer."""


@dataclass(frozen=True)
class Rubric:
    instructions: str
    levels: list[str]  # worst to best: the rubric file's `criteria`


@dataclass(frozen=True)
class Answer:
    score: float  # expected level, 0 to len(levels) - 1
    confidence: float
    probabilities: dict[int, float]  # level -> probability


class Judge(Protocol):
    name: str  # "typesafe" or "openai"
    model: str  # for report headers

    def score(self, text: str, rubrics: dict[str, Rubric]) -> dict[str, Answer]: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Judge": ...
    def __exit__(self, *exc) -> None: ...


def make_judge(name, retries=None):
    """A judge by name. retries=None keeps the provider's default; 0 turns retries off."""
    if name == "typesafe":
        from judges.typesafe import TypeSafeJudge
        return TypeSafeJudge(retries=retries)
    raise ValueError(f"unknown judge {name!r}; choose one of: {', '.join(NAMES)}")
```

- [ ] **Step 4: Write `evals/judges/typesafe.py`**

```python
"""Adapter for TypeSafe's Jev."""
import os

from typesafe_sdk import RetryPolicy, Score, TypeSafeClient, TypeSafeError
from typesafe_sdk.constants import DEFAULT_MODEL, DEFAULT_MODEL_ENV

from judges import Answer, JudgeError


class TypeSafeJudge:
    name = "typesafe"

    def __init__(self, client=None, retries=None):
        if client is None:
            try:
                client = (
                    TypeSafeClient() if retries is None
                    else TypeSafeClient(retry=RetryPolicy(max_retries=retries))
                )
            except TypeSafeError as e:
                raise JudgeError(str(e)) from e
        self._client = client
        # The SDK's own default: TYPESAFE_DEFAULT_MODEL when set, else jev-latest.
        self.model = os.environ.get(DEFAULT_MODEL_ENV, "").strip() or DEFAULT_MODEL

    def score(self, text, rubrics):
        questions = {
            name: Score(instructions=r.instructions, criteria=r.levels)
            for name, r in rubrics.items()
        }
        try:
            response = self._client.system_one(state=text, questions=questions)
        except TypeSafeError as e:
            raise JudgeError(str(e)) from e
        missing = [name for name in rubrics if name not in response.answers]
        if missing:
            raise JudgeError(f"no answer for {', '.join(missing)}")
        return {
            name: Answer(
                score=answer.score,
                confidence=answer.confidence,
                probabilities=dict(answer.probabilities),
            )
            for name, answer in response.answers.items()
            if name in rubrics
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
```

- [ ] **Step 5: Add the package to the test workflow's path filters**

In `.github/workflows/test.yml`, add `- "evals/judges/**"` on the line after `- "evals/scoring.py"`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_judges.py tests/test_typesafe_judge.py`
Expected: `11 passed`

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `56 passed`

- [ ] **Step 7: Commit**

```bash
git add evals/judges/__init__.py evals/judges/typesafe.py tests/test_judges.py tests/test_typesafe_judge.py .github/workflows/test.yml
git commit -m "Add the judge interface and a TypeSafe adapter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Score through the interface

Switch `scoring.score_text` and its callers from the TypeSafe client to a judge. The retry test moves out of `test_scoring.py`; Task 3 already covers it in the adapter's tests.

**Files:**
- Modify: `evals/scoring.py`, `evals/score_evals.py`, `ci/clean_mode_check.py`, `ci/render.py`
- Rewrite: `tests/fake_judge.py`
- Modify: `tests/test_scoring.py`, `tests/test_cli.py`, `tests/test_render.py`

- [ ] **Step 1: Rewrite `tests/fake_judge.py` as a fake judge**

```python
"""A stand-in judge that records calls and never touches the network."""
from judges import Answer, JudgeError


class FakeJudge:
    """Answers every rubric at `level`, or at `levels[name]` when given.

    Raises JudgeError for any call whose text contains `fail_on`.
    """

    name = "fake"
    model = "fake-model"

    def __init__(self, level=3, levels=None, fail_on=None, error_message="fake outage"):
        self.level = level
        self.levels = levels or {}
        self.fail_on = fail_on
        self.error_message = error_message
        self.calls = []

    def score(self, text, rubrics):
        self.calls.append({"text": text, "rubrics": rubrics})
        if self.fail_on and self.fail_on in text:
            raise JudgeError(self.error_message)
        return {name: _answer(self.levels.get(name, self.level)) for name in rubrics}

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _answer(level):
    return Answer(score=float(level), confidence=0.9, probabilities={level: 1.0})
```

- [ ] **Step 2: Point the existing tests at the fake judge**

```bash
perl -pi -e 's/\bFakeJevClient\b/FakeJudge/g; s/\["state"\]/["text"]/g; s/\bclient=client\b/judge=client/g' \
  tests/test_cli.py tests/test_render.py tests/test_scoring.py
perl -pi -e 's/\bclient\b/judge/g' tests/test_cli.py tests/test_render.py tests/test_scoring.py
perl -pi -e 's/test_one_failed_jev_call_marks_only_that_item/test_one_failed_judge_call_marks_only_that_item/' tests/test_cli.py
perl -pi -e 's/test_weakest_shows_the_level_jev_found_most_likely/test_weakest_shows_the_level_the_judge_found_most_likely/' tests/test_render.py
```

This makes `main(..., client=...)` calls into `main(..., judge=...)`, turns `calls[...]["state"]` into `["text"]`, and renames the `client` variables to `judge`.

Then in `tests/test_scoring.py`:
- delete `test_make_client_can_turn_retries_off` (the last test in the file)
- add `from judges import Rubric` below `from fake_judge import FakeJudge`
- append:

```python
def test_each_rubric_group_is_one_judge_call_with_its_filled_layout():
    judge = FakeJudge()
    config = scoring.load_config()
    scoring.score_text(judge, config, SAMPLE_DOC, source=SAMPLE_SOURCE)
    document_call, source_call = judge.calls
    assert document_call["text"] == SAMPLE_DOC
    padding = config.dimensions["padding"]
    assert document_call["rubrics"]["padding"] == Rubric(padding["instructions"], padding["criteria"])
    assert SAMPLE_SOURCE in source_call["text"] and SAMPLE_DOC in source_call["text"]
    assert "requirements_retained" in source_call["rubrics"]


def test_probability_keys_are_strings_for_the_saved_scores():
    raw = scoring.score_text(
        FakeJudge(level=2), scoring.load_config(), SAMPLE_DOC, states={scoring.DOCUMENT_ONLY}
    )
    assert raw["padding"]["probabilities"] == {"2": 1.0}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `30 failed, 27 passed`. The failures are `AttributeError: 'FakeJudge' object has no attribute 'system_one'` and `TypeError: main() got an unexpected keyword argument 'judge'`.

- [ ] **Step 4: Switch `evals/scoring.py` to the interface**

Replace the module docstring with:

```python
"""Shared scoring for the clean-mode evals and the clean-mode CI check.

Loads the rubrics in dimensions.json, asks a judge to score a document
against them, and adds the composite rubrics. Raises instead of exiting, so
each caller decides how to fail.
"""
```

Replace `from typesafe_sdk import RetryPolicy, Score, TypeSafeClient, TypeSafeError` with `from judges import Rubric`.

Replace `__all__` with:

```python
__all__ = [
    "Config", "ConfigError", "DOCUMENT_ONLY", "load_config", "score_text",
]
```

Replace `Config.questions_by_state` with:

```python
    def rubrics_by_state(self, states=None):
        grouped = {}
        for name, entry in self.dimensions.items():
            state = entry.get("state", DOCUMENT_ONLY)
            if states is None or state in states:
                grouped.setdefault(state, {})[name] = Rubric(entry["instructions"], entry["criteria"])
        return grouped
```

Delete `make_client` entirely. In `score_text`, rename the first parameter `client` to `judge` and replace the loop's call with one `judge.score` per group:

```python
def score_text(judge, config, text, source=None, states=None):
    # docstring unchanged
    raw = {}
    for state, rubrics in config.rubrics_by_state(states).items():
        template = config.state_templates[state]
        if "{source}" in template and source is None:
            continue
        answers = judge.score(template.format(document=text, source=source or ""), rubrics)
        raw.update({
            name: {
                "score": answer.score,
                "confidence": answer.confidence,
                "probabilities": {str(k): v for k, v in answer.probabilities.items()},
            }
            for name, answer in answers.items()
        })
    # the composites loop below is unchanged
```

- [ ] **Step 5: Switch the check command to the interface**

In `ci/clean_mode_check.py`, add `import judges  # noqa: E402` on the line before `import scoring  # noqa: E402`, then replace `score_items` with:

```python
def score_items(judge, config, items):
    """Score (label, text) pairs. A failed judge call marks only its own item."""
    results = []
    for label, text in items:
        try:
            raw = scoring.score_text(judge, config, text, states={scoring.DOCUMENT_ONLY})
            results.append(ItemResult(label, raw))
        except judges.JudgeError as e:
            print(f"::warning::{escape_command(f'could not score {label}: {e}')}")
            results.append(ItemResult(label, None, "could not score"))
    return results
```

Change the `main` signature to:

```python
def main(argv=None, judge=None, post=upsert_comment, fetch=fetch_pull_request):
```

and the scoring block near the end of `main` to:

```python
    with judge or judges.make_judge("typesafe", retries=0) as active:
        results = score_items(active, config, items) + unscored
```

Task 7 replaces `"typesafe"` with the `--judge` value.

- [ ] **Step 6: Switch the eval scorer to the interface**

In `evals/score_evals.py`, replace the import block with:

```python
try:
    import judges
    import scoring
except ImportError as e:
    sys.exit(f"could not import the scoring modules ({e}). Run: pip install -r evals/requirements.txt")
```

and in `score_texts` replace `with scoring.make_client() as client:` with `with judges.make_judge("typesafe") as judge:`, and `scoring.score_text(client, ...)` with `scoring.score_text(judge, ...)`. Task 6 moves the judge out to `main`.

- [ ] **Step 7: Drop "Jev" from `ci/render.py`'s docstrings**

- `"""Turn Jev scores into the Markdown summary posted on the pull request."""` → `"""Turn judge scores into the Markdown summary posted on the pull request."""`
- `"""Criterion text for the level Jev found most likely."""` → `"""Criterion text for the level the judge found most likely."""`

- [ ] **Step 8: Run the tests to verify they pass**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `57 passed`

Run: `git grep -n "TypeSafeError\|make_client\|questions_by_state" -- evals ci tests`
Expected: matches only in `evals/judges/typesafe.py` and `tests/test_typesafe_judge.py`

- [ ] **Step 9: Commit**

```bash
git add evals/scoring.py evals/score_evals.py ci/clean_mode_check.py ci/render.py \
  tests/fake_judge.py tests/test_scoring.py tests/test_cli.py tests/test_render.py
git commit -m "Score through the judge interface instead of the TypeSafe client" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: OpenAI adapter

**Files:**
- Create: `evals/judges/openai.py`, `tests/test_openai_judge.py`
- Modify: `evals/judges/__init__.py`, `tests/test_judges.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_openai_judge.py` builds real `openai.types.decision.Decision` objects with `Decision.model_validate`, the same validation the library runs on a live reply.

```python
from types import SimpleNamespace

import pytest
from openai import OpenAIError
from openai.types.decision import Decision

from judges import Answer, JudgeError, Rubric
from judges import openai as openai_judge

RUBRICS = {
    "padding": Rubric(instructions="Is it padded?", levels=["very", "a little", "not at all"]),
    "economy": Rubric(instructions="Is it economical?", levels=["no", "yes"]),
}


def decision(answers):
    """A real Decision, validated the way the library parses OpenAI's reply."""
    return Decision.model_validate({
        "model": openai_judge.MODEL,
        "usage": {
            "input_tokens": 10, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
            "output_tokens": 2, "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 12,
        },
        "answers": answers,
    })


def score_answer(name, score, probabilities):
    return {
        "type": "score", "name": name, "score": score, "confidence": 0.7,
        "probabilities": [
            {"value": level, "label": f"level {level}", "probability": p}
            for level, p in probabilities.items()
        ],
    }


class StandInClient:
    """Mimics OpenAI's client: records decisions.create calls and returns a canned result or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.closed = False
        self.decisions = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self):
        self.closed = True


def both_answered():
    return decision([
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
        score_answer("economy", 0.9, {0: 0.1, 1: 0.9}),
    ])


def test_sends_every_rubric_as_a_named_score_question_in_one_request():
    client = StandInClient(both_answered())
    openai_judge.OpenAIJudge(client=client).score("the doc", RUBRICS)
    (call,) = client.calls
    assert call["model"] == "gpt-6-luna"
    assert call["input"] == "the doc"
    assert call["questions"] == [
        {
            "type": "score", "name": "padding", "instructions": "Is it padded?",
            "levels": [
                {"label": "level 0", "description": "very"},
                {"label": "level 1", "description": "a little"},
                {"label": "level 2", "description": "not at all"},
            ],
        },
        {
            "type": "score", "name": "economy", "instructions": "Is it economical?",
            "levels": [
                {"label": "level 0", "description": "no"},
                {"label": "level 1", "description": "yes"},
            ],
        },
    ]


def test_matches_answers_by_name_even_out_of_order():
    reversed_order = decision([
        score_answer("economy", 0.9, {0: 0.1, 1: 0.9}),
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
    ])
    answers = openai_judge.OpenAIJudge(client=StandInClient(reversed_order)).score("doc", RUBRICS)
    assert answers["padding"] == Answer(score=1.5, confidence=0.7, probabilities={0: 0.1, 1: 0.3, 2: 0.6})
    assert answers["economy"] == Answer(score=0.9, confidence=0.7, probabilities={0: 0.1, 1: 0.9})


def test_a_refusal_raises_judge_error():
    refused = decision([
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
        {"type": "refusal", "name": "economy"},
    ])
    with pytest.raises(JudgeError, match="refused.*economy"):
        openai_judge.OpenAIJudge(client=StandInClient(refused)).score("doc", RUBRICS)


def test_a_missing_answer_raises_judge_error():
    partial = decision([score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6})])
    with pytest.raises(JudgeError, match="no answer for economy"):
        openai_judge.OpenAIJudge(client=StandInClient(partial)).score("doc", RUBRICS)


def test_openai_errors_become_judge_errors():
    client = StandInClient(OpenAIError("rate limited"))
    with pytest.raises(JudgeError, match="rate limited"):
        openai_judge.OpenAIJudge(client=client).score("doc", RUBRICS)


def test_retries_zero_reaches_the_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with openai_judge.OpenAIJudge(retries=0) as judge:
        assert judge._client.max_retries == 0


def test_a_missing_key_raises_judge_error_naming_it(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(JudgeError, match="OPENAI_API_KEY"):
        openai_judge.OpenAIJudge()


def test_closing_the_judge_closes_the_client():
    client = StandInClient(both_answered())
    with openai_judge.OpenAIJudge(client=client) as judge:
        assert (judge.name, judge.model) == ("openai", "gpt-6-luna")
    assert client.closed
```

Constructing `OpenAI()` with a key makes no network call, so the retries test stays offline.

In `tests/test_judges.py`, replace the imports with:

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest

import judges

EVALS = Path(__file__).resolve().parent.parent / "evals"
```

and append:

```python
def test_make_judge_builds_the_openai_judge(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with judges.make_judge("openai") as judge:
        assert judge.name == "openai"


def test_choosing_typesafe_does_not_import_openai():
    code = "import sys, judges; judges.make_judge('typesafe'); print('openai' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=EVALS, capture_output=True, text=True, check=True,
        env={**os.environ, "TYPESAFE_API_KEY": "test-key"},
    )
    assert result.stdout.strip() == "False"


def test_choosing_openai_does_not_import_typesafe():
    code = "import sys, judges; judges.make_judge('openai'); print('typesafe_sdk' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=EVALS, capture_output=True, text=True, check=True,
        env={**os.environ, "OPENAI_API_KEY": "test-key"},
    )
    assert result.stdout.strip() == "False"
```

The last two tests run in a fresh interpreter, because this test session has already imported both libraries.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_openai_judge.py`
Expected: collection error, `ImportError: cannot import name 'openai' from 'judges'`

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_judges.py`
Expected: `2 failed, 4 passed`: `test_make_judge_builds_the_openai_judge` with `ValueError: unknown judge 'openai'; choose one of: typesafe, openai`, and `test_choosing_openai_does_not_import_typesafe` with `CalledProcessError` (the same `ValueError`, in the child interpreter)

- [ ] **Step 3: Write `evals/judges/openai.py`**

Inside the `judges` package, `from openai import ...` still means the top-level library: Python 3 imports are absolute.

```python
"""Adapter for OpenAI's Decisions API."""
from openai import OpenAI, OpenAIError

from judges import Answer, JudgeError

# The model OpenAI's Decisions guide names.
MODEL = "gpt-6-luna"


class OpenAIJudge:
    name = "openai"
    model = MODEL

    def __init__(self, client=None, retries=None):
        if client is None:
            try:
                client = OpenAI() if retries is None else OpenAI(max_retries=retries)
            except OpenAIError as e:
                raise JudgeError(str(e)) from e
        self._client = client

    def score(self, text, rubrics):
        questions = [
            {
                "type": "score",
                "name": name,
                "instructions": rubric.instructions,
                "levels": [
                    {"label": f"level {i}", "description": level}
                    for i, level in enumerate(rubric.levels)
                ],
            }
            for name, rubric in rubrics.items()
        ]
        try:
            decision = self._client.decisions.create(model=MODEL, input=text, questions=questions)
        except OpenAIError as e:
            raise JudgeError(str(e)) from e
        by_name = {answer.name: answer for answer in decision.answers}
        answers = {}
        for name in rubrics:
            answer = by_name.get(name)
            if answer is None:
                raise JudgeError(f"no answer for {name}")
            if answer.type == "refusal":
                raise JudgeError(f"OpenAI refused to score {name}")
            if answer.type != "score":
                raise JudgeError(f"expected a score for {name}, got a {answer.type}")
            answers[name] = Answer(
                score=answer.score,
                confidence=answer.confidence,
                probabilities={p.value: p.probability for p in answer.probabilities},
            )
        return answers

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
```

- [ ] **Step 4: Register it in `make_judge`**

In `evals/judges/__init__.py`, add before the `raise ValueError(...)` line:

```python
    if name == "openai":
        from judges.openai import OpenAIJudge
        return OpenAIJudge(retries=retries)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `68 passed`

- [ ] **Step 6: Commit**

```bash
git add evals/judges/openai.py evals/judges/__init__.py tests/test_openai_judge.py tests/test_judges.py
git commit -m "Add an OpenAI Decisions API judge" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Chunk 3: Choosing the judge

### Task 6: `--judge` in the eval scorer

**Files:**
- Modify: `evals/score_evals.py`, `evals/run_evals.sh`
- Create: `tests/test_score_evals.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_score_evals.py`. The fixture saves a source prompt next to the report: without one, the source-comparing rubrics go unscored and the scorer's console printout (`print_report`) raises a `KeyError`, a gap that predates this change.

````python
import pytest

import score_evals
from fake_judge import FakeJudge

REPORT = """# Clean-mode scoring report

## clean-mode-demo

<details><summary>with outputs (1 run(s))</summary>

**Run 1**

```markdown
# Demo

Short and clear.
```

</details>
"""


@pytest.fixture
def saved_report(tmp_path):
    """A saved report plus the case's source prompt, laid out like the plugin root."""
    case = tmp_path / "evals" / "clean-mode-demo"
    case.mkdir(parents=True)
    (case / "prompt.md").write_text("Write a short demo doc.")
    path = tmp_path / "report.md"
    path.write_text(REPORT)
    return path


def test_report_header_names_the_judge_and_model(tmp_path):
    texts = {"clean-mode-demo__with__0": "# Demo"}
    scored = {key: {} for key in texts}
    path = score_evals.write_markdown_report(scored, texts, tmp_path, "clean-mode-*", FakeJudge())
    assert path.parent.name.endswith("-fake")
    report = path.read_text()
    assert report.startswith("# Clean-mode scoring report\n")
    assert "judge `fake` (model `fake-model`)" in report


def test_main_scores_with_the_chosen_judge(saved_report, tmp_path, monkeypatch):
    chosen = []

    def make_judge(name):
        chosen.append(name)
        return FakeJudge()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(score_evals.judges, "make_judge", make_judge)
    score_evals.main(["--from-report", str(saved_report), "--judge", "openai", "--plugin-root", str(tmp_path)])
    assert chosen == ["openai"]
    (report,) = (tmp_path / "evals" / "results").glob("*-fake/report.md")
    assert "Short and clear." in report.read_text()


def test_missing_key_names_the_chosen_judges_key(saved_report, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        score_evals.main(["--from-report", str(saved_report), "--judge", "openai", "--plugin-root", str(tmp_path)])


def test_typesafe_is_the_default_judge(saved_report, tmp_path, monkeypatch):
    chosen = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(score_evals.judges, "make_judge", lambda name: chosen.append(name) or FakeJudge())
    score_evals.main(["--from-report", str(saved_report), "--plugin-root", str(tmp_path)])
    assert chosen == ["typesafe"]


def test_missing_key_stops_before_running_an_eval(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(score_evals, "run_eval", lambda *args: pytest.fail("ran an eval without a key"))
    with pytest.raises(SystemExit, match="TYPESAFE_API_KEY is not set"):
        score_evals.main([])
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_score_evals.py`
Expected: `5 failed`: four `TypeError: main() takes 0 positional arguments but 1 was given`, one `TypeError` from passing a judge where `write_markdown_report` expects a folder path

- [ ] **Step 3: Update the docstring and comments**

In `evals/score_evals.py`, the docstring's usage block becomes:

```
    pip install -r evals/requirements.txt
    export TYPESAFE_API_KEY=...    # or OPENAI_API_KEY with --judge openai
    python3 evals/score_evals.py [--judge typesafe|openai]
```

its first line becomes `"""Score clean-mode with/without outputs with a judging model.`, and its last sentence (from `play; Jev is the sole judge.` to the end) becomes:

```
play; the chosen judge (TypeSafe's Jev by default, or OpenAI's Decisions API)
is the only one. Use --from to re-score an existing `claude plugin eval
--json` result instead of running a new eval, or --from-report to re-score a
saved report's outputs, for example with the other judge.
```

Comment edits (leave "per Jev's guidance" alone: it records where the atomic-question rule came from):
- `so both ask Jev identical` → `so both ask the judge identical`
- `means a second Jev call against a different state.` → `means a second judge call against a different layout.`
- `# A Jev score is a position` → `# A score is a position`
- in `texts_from_report`: `one Jev call per output` → `one judge call per output`

- [ ] **Step 4: Take the judge as a parameter**

`score_texts` takes the judge instead of making one:

```python
def score_texts(judge, texts, sources=None):
    sources = sources or {}
    skipped = set()
    scored = {}
    for key, text in texts.items():
        case = key.rsplit("__", 2)[0]
        if case not in sources:
            skipped.add(case)
        scored[key] = scoring.score_text(judge, CONFIG, text, source=sources.get(case))
    # the warning loop and return are unchanged
```

`write_markdown_report` gains a `judge` parameter, names its folder after the judge, and prints the judge in the header:

```python
def write_markdown_report(scored, texts, plugin_root, case_glob, judge, out_dir=None):
    grouped = group_by_case(scored)
    runs = max((len(arms["with"]) for arms in grouped.values()), default=0)
    generated_at = datetime.now(timezone.utc)
    out_dir = Path(out_dir) if out_dir else Path(plugin_root) / "evals" / "results" / (generated_at.strftime("%Y-%m-%dT%H-%M-%S") + f"-{judge.name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"

    lines = [
        "# Clean-mode scoring report",
        "",
        f"Generated {generated_at.strftime('%Y-%m-%dT%H:%M:%SZ')} · judge `{judge.name}` (model `{judge.model}`) · "
        f"case filter `{case_glob}` · {runs} run(s) per arm.",
        # the rest is unchanged
```

- [ ] **Step 5: Add `--judge` to `main`**

`def main():` becomes `def main(argv=None):`. Replace the `--out` argument and `parse_args` call with:

```python
    parser.add_argument("--judge", choices=judges.NAMES, default="typesafe", help="which judging model scores the outputs")
    parser.add_argument("--out", help="write raw scores as JSON to this path")
    args = parser.parse_args(argv)
    # Check the key before running an eval, which is slow and costs money.
    key = judges.API_KEY_ENV[args.judge]
    if not os.environ.get(key):
        sys.exit(f"{key} is not set; the {args.judge} judge needs it")
```

Add `import os` to the imports, between `import json` and `import re`.

Replace the scoring and report lines with:

```python
    # A judge failure ends the run: an eval report with gaps is not worth comparing.
    try:
        with judges.make_judge(args.judge) as judge:
            scored = score_texts(judge, texts, load_sources(args.plugin_root))
    except judges.JudgeError as e:
        sys.exit(f"{args.judge} judge failed: {e}")
    print_report(scored, texts)

    report_path = write_markdown_report(scored, texts, args.plugin_root, args.case, judge)
```

The early key check replaces the one `run_evals.sh` used to make, and covers both judges. A key the provider rejects still surfaces as a `JudgeError`.

- [ ] **Step 6: Stop the run script checking for a TypeSafe key**

In `evals/run_evals.sh`, delete the `if [ -z "${TYPESAFE_API_KEY:-}" ]; then ... fi` block and the blank line after it. The scorer now reports a missing key for whichever judge was chosen.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `73 passed`

- [ ] **Step 8: Commit**

```bash
git add evals/score_evals.py evals/run_evals.sh tests/test_score_evals.py
git commit -m "Let the eval scorer choose its judge with --judge" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: `--judge` in the pull request check

**Files:**
- Modify: `ci/clean_mode_check.py`, `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, make the existing missing-key test also check the notice:

```python
def test_missing_api_key_skips_without_posting(pr, monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    judge, post = FakeJudge(), RecordingPost()
    assert run(pr, judge, post) == 0
    assert judge.calls == [] and post.calls == []
    assert "::notice::TYPESAFE_API_KEY is not set" in capsys.readouterr().out
```

and append:

```python
def test_missing_key_notice_names_the_chosen_judges_key(pr, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    judge, post = FakeJudge(), RecordingPost()
    assert run(pr, judge, post, extra=["--judge", "openai"]) == 0
    assert judge.calls == [] and post.calls == []
    assert "::notice::OPENAI_API_KEY is not set" in capsys.readouterr().out


def test_judge_flag_builds_that_judge_with_retries_off(pr, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    built = []

    def make_judge(name, retries=None):
        built.append((name, retries))
        return FakeJudge()

    monkeypatch.setattr(clean_mode_check.judges, "make_judge", make_judge)
    assert clean_mode_check.main(
        ["--event-path", str(pr["event"]), "--judge", "openai"], post=RecordingPost()
    ) == 0
    assert built == [("openai", 0)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q tests/test_cli.py`
Expected: `2 failed, 17 passed`, both `SystemExit: 2` with `unrecognized arguments: --judge openai`

- [ ] **Step 3: Add the flag and use it**

In `ci/clean_mode_check.py`, the docstring's first lines become:

```python
"""Score the prose in a pull request against clean-mode with a judging model.

Advisory: weak prose or an outage at the judge or GitHub never fails the run.
Bugs in this tool or in dimensions.json do.

    python ci/clean_mode_check.py --base main --pr-title "..." --pr-body-file body.md [--judge openai]
```

The comment above `DEFAULT_MAX_CHARS` becomes:

```python
# TypeSafe's Jev accepts at most 32k tokens for the document plus its longest
# question (about 400 tokens today). At a worst case of 2.5 characters per
# token (code-heavy Markdown), 75,000 characters is about 30k tokens, leaving
# room. OpenAI publishes no limit for its Decisions API, so the same cap
# applies to both judges.
```

In `parse_args`, after the `--post` argument:

```python
    parser.add_argument("--judge", choices=judges.NAMES, default="typesafe", help="which judging model scores the prose")
```

In `main`, the key check becomes:

```python
    key = judges.API_KEY_ENV[args.judge]
    if not os.environ.get(key):
        print(f"::notice::{key} is not set (normal for PRs from forks); skipping the clean-mode check")
        return 0
```

and the judge line becomes `with judge or judges.make_judge(args.judge, retries=0) as active:`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `75 passed`

Run: `env -u OPENAI_API_KEY -u GITHUB_EVENT_PATH evals/.venv/bin/python ci/clean_mode_check.py --judge openai --base HEAD~1; echo "exit $?"`
Expected: `::notice::OPENAI_API_KEY is not set (normal for PRs from forks); skipping the clean-mode check`, then `exit 0`

- [ ] **Step 5: Commit**

```bash
git add ci/clean_mode_check.py tests/test_cli.py
git commit -m "Let the pull request check choose its judge with --judge" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: Action inputs and README

**Files:**
- Modify: `.github/actions/clean-mode-check/action.yml`, `.github/actions/clean-mode-check/README.md`

- [ ] **Step 1: Add the inputs to `action.yml`**

Inputs reach the shell as environment variables, never as `${{ }}` inside `run`, so an input cannot inject shell code.

The `description` and first input become:

```yaml
description: Score a pull request's prose against clean-mode with TypeSafe or OpenAI and post one advisory comment.
inputs:
  judge:
    description: Which judging model scores the prose, typesafe or openai.
    required: false
    default: typesafe
  typesafe-api-key:
    description: TypeSafe API key, used when judge is typesafe. If empty, the check skips.
    required: false
    default: ""
  openai-api-key:
    description: OpenAI API key, used when judge is openai. If empty, the check skips.
    required: false
    default: ""
```

In the "Score prose" step's `env`, put `JUDGE: ${{ inputs.judge }}` before `TYPESAFE_API_KEY` and `OPENAI_API_KEY: ${{ inputs.openai-api-key }}` after it. In its `run`, add `--judge "$JUDGE"` on the line after `... ci/clean_mode_check.py" --post`:

```yaml
      run: >
        "$RUNNER_TEMP/clean-mode-venv/bin/python" "$GITHUB_ACTION_PATH/../../../ci/clean_mode_check.py" --post
        --judge "$JUDGE"
        --include "$INCLUDE" --max-files "$MAX_FILES"
        --max-chars "$MAX_CHARS" --min-lines "$MIN_LINES"
```

No change to the install step: `evals/requirements.txt` now carries both libraries, so every run installs both.

Run: `evals/.venv/bin/python -c "import yaml; d = yaml.safe_load(open('.github/actions/clean-mode-check/action.yml')); print(list(d['inputs'])); print(d['runs']['steps'][2]['run'])"`
Expected: `['judge', 'typesafe-api-key', 'openai-api-key', 'github-token', 'include', 'max-files', 'max-chars', 'min-lines']`, then one command line containing `--post --judge "$JUDGE" --include`

- [ ] **Step 2: Run the clean-mode skill**

Call the Skill tool with `clean-mode` before editing the README, and apply it to the new text.

- [ ] **Step 3: Update the README**

Line 5, `Scoring uses Jev, a judging model from TypeSafe.`, becomes:

```markdown
Scoring uses a judging model: TypeSafe's Jev by default, or OpenAI's Decisions API.
```

Setup step 1 becomes:

```markdown
1. Add an API key as a repository secret: `TYPESAFE_API_KEY` for TypeSafe (the default), or `OPENAI_API_KEY` for OpenAI.
```

Between the workflow YAML block and `Keep both permissions.`, add:

````markdown
To use OpenAI, replace the action's `with:` lines with:

```yaml
        with:
          judge: openai
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
```
````

In the settings table, the `typesafe-api-key` row becomes three rows:

```markdown
| `judge` | `typesafe` | Which judging model scores the prose: `typesafe` or `openai`. |
| `typesafe-api-key` | none | Used when `judge` is `typesafe`. Without it, the check skips. |
| `openai-api-key` | none | Used when `judge` is `openai`. Without it, the check skips. |
```

and the `max-chars` row ends `Keeps each doc within TypeSafe's size limit; OpenAI publishes none. |` instead of `Keeps each doc within Jev's size limit. |`.

Run: `git grep -n -i jev .github`
Expected: one match, the README's "TypeSafe's Jev by default" line

- [ ] **Step 4: Commit**

```bash
git add .github/actions/clean-mode-check/action.yml .github/actions/clean-mode-check/README.md
git commit -m "Add judge and openai-api-key inputs to the clean-mode action" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Chunk 4: Verification and rollout

### Task 9: Final checks

- [ ] **Step 1: Full test run**

Run: `env -u TYPESAFE_API_KEY -u OPENAI_API_KEY evals/.venv/bin/python -m pytest -q`
Expected: `75 passed`

- [ ] **Step 2: No stale names**

Run: `git grep -n "jev_core\|score_with_jev\|run_jev\|fake_jev\|FakeJevClient\|clean-mode:jev\|make_client" -- ':!docs'`
Expected: no output

- [ ] **Step 3: No em-dashes in the changed files**

The eval prompts (`evals/clean-mode-*/prompt.md`) contain em-dashes on purpose and are not touched here.

Run: `BASE=$(git log --format=%H -1 -- docs/superpowers/specs/2026-10-13-swappable-judge-design.md); git diff --name-only --diff-filter=AMR "$BASE" HEAD | xargs grep -n "$(printf '\342\200\224')"; git log --format=%B "$BASE"..HEAD | grep -n "$(printf '\342\200\224')"`
Expected: no output from either grep

- [ ] **Step 4: Old reports still parse**

Re-scoring reads outputs back out of saved reports, including the old `-jev` folders.

Run: `evals/.venv/bin/python -c "import sys; sys.path.insert(0, 'evals'); import score_evals; print(len(score_evals.texts_from_report('evals/results/2026-10-02T01-55-47-jev/report.md')))"`
Expected: `8`. If that folder is gone, pick any `evals/results/*-jev/report.md` and expect a nonzero count.

### Task 10: Live check with both judges

This task spends API credit with both providers. **Ask the user before running it**, and say which report you will use and roughly how many calls it makes.

- [ ] **Step 1: Ask the user**

Suggest the smallest saved report, `evals/results/2026-10-02T01-55-47-jev/report.md` (8 outputs, so about 16 calls per judge: one per output, plus one more for the source-comparing rubrics). Confirm both `TYPESAFE_API_KEY` and `OPENAI_API_KEY` are set in their shell, or ask them to export them. Do not continue without a yes.

- [ ] **Step 2: Re-score with TypeSafe**

Run from the repo root: `evals/.venv/bin/python evals/score_evals.py --from-report evals/results/2026-10-02T01-55-47-jev/report.md --judge typesafe`
Expected: per-case scores print, then `Report: evals/results/<timestamp>-typesafe/report.md`. The new report's header reads ``judge `typesafe` (model `jev-latest`)``.

- [ ] **Step 3: Re-score with OpenAI**

Run: `evals/.venv/bin/python evals/score_evals.py --from-report evals/results/2026-10-02T01-55-47-jev/report.md --judge openai`
Expected: `Report: evals/results/<timestamp>-openai/report.md`, header ``judge `openai` (model `gpt-6-luna`)``. If it exits with `openai judge failed: ...`, show the user the message; a refusal or an unknown model name surfaces here.

- [ ] **Step 4: Report back**

Show the user both reports' "Overall" tables side by side. Both runs must score every case; the numbers will differ between judges. Nothing to commit: `evals/results/` is gitignored.

### Task 11: Rollout hand-off

These touch a pull request and another branch, so check with the user first.

- [ ] **Step 1: Ask where this lands**

Ask whether to push `feat/swappable-judge` and fold it into pull request #4, or open it as a follow-up pull request right after #4.

- [ ] **Step 2: Flag the comment check's plan**

Tell the user that `docs/superpowers/plans/2026-10-07-clean-mode-comment-check.md` on branch `feat/clean-mode-comment-check` still uses the old names (`jev_core`, `make_client`, `FakeJevClient`, `client=`, `calls[...]["state"]`). Once they agree, update it on that branch and have a reviewer check that every code block fits the new interface (`scoring`, `judges.make_judge`, `FakeJudge`, `judge=`, `calls[...]["text"]`).
