# Clean-mode CI Check Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reusable GitHub Action that scores changed Markdown docs and the PR description against clean-mode with Jev, and posts one advisory PR comment.

**Architecture:** A new shared module, `evals/jev_core.py`, owns rubric loading and Jev calls for both the existing eval scorer and the new CI CLI. The CLI (`ci/clean_mode_check.py`) is split into small modules: collect changed docs, render the comment, post the comment. A composite action wraps the CLI.

**Tech Stack:** Python 3.12, `typesafe-sdk` 0.7.2 (Jev), pytest, git, GitHub REST API via `urllib`, GitHub composite actions.

**Spec:** [docs/superpowers/specs/2026-10-07-clean-mode-ci-check-design.md](../specs/2026-10-07-clean-mode-ci-check-design.md)

---

## Before you start

- Branch: create `feat/clean-mode-ci-check` from `eval/clean-mode-dimensions-v2` (the spec is committed there).
- Python: use `evals/.venv/bin/python`. Create it with `python3 -m venv evals/.venv` if missing.
- Repo rules (from `CLAUDE.md` and memory): no em-dashes in prose or comments; American spelling in new text ("normalized"); run the `clean-mode` skill before writing any README.
- SDK facts this plan relies on:
  - `ScoreAnswer.score` is a float: the probability-weighted mean of levels. `probabilities` maps int level to probability.
  - `TypeSafeClient` retries by default. `TypeSafeClient(retry=RetryPolicy(max_retries=0))` turns that off; the spec says no retries.
  - All SDK errors subclass `typesafe_sdk.TypeSafeError`.

## File map

| File | Responsibility |
|---|---|
| `evals/jev_core.py` | Create. Load and validate `dimensions.json`, build Jev questions, call Jev, compute composites |
| `evals/score_with_jev.py` | Modify. Use `jev_core` instead of its own config and scoring code |
| `evals/requirements.txt` | Modify. Pin versions |
| `evals/requirements-dev.txt` | Create. Adds pytest |
| `ci/collect.py` | Create. Find changed docs via git, choose which to score |
| `ci/render.py` | Create. Overall score, weakest rubrics, Markdown comment |
| `ci/post_comment.py` | Create. Create or update the marked PR comment |
| `ci/clean_mode_check.py` | Create. CLI entry point wiring the above |
| `tests/` | Create. `conftest.py`, `fake_jev.py`, fixtures, one test file per module |
| `pytest.ini` | Create. Points pytest at `tests/` |
| `.github/actions/clean-mode-check/action.yml` | Create. Composite action |
| `.github/actions/clean-mode-check/README.md` | Create. How a repo adopts the action |
| `.github/workflows/test.yml` | Create. Runs pytest |
| `.github/workflows/clean-mode-check.yml` | Create. Runs the action on this repo's PRs (end-to-end check) |

---

## Chunk 1: Shared scoring core

### Task 1: Test setup and the pre-refactor snapshot

Captures exactly what the current eval scorer sends to Jev, so Task 2 can prove `jev_core` sends the same.

**Files:**
- Create: `pytest.ini`, `evals/requirements-dev.txt`, `tests/conftest.py`, `tests/fake_jev.py`
- Create: `tests/fixtures/sample_doc.md`, `tests/fixtures/sample_source.md`, `tests/fixtures/jev_calls_before_refactor.json`

- [ ] **Step 1: Add pytest config and dev requirements**

`pytest.ini`:

```ini
[pytest]
testpaths = tests
```

`evals/requirements-dev.txt`:

```
-r requirements.txt
pytest==8.4.2
```

Run: `evals/.venv/bin/pip install -r evals/requirements-dev.txt`
Expected: installs pytest; typesafe-sdk already present.

- [ ] **Step 2: Add `tests/conftest.py`**

```python
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for folder in ("evals", "ci", "tests"):
    sys.path.insert(0, str(ROOT / folder))


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A git repo on branch main with one base commit of three docs."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "test")
    (tmp_path / "keep.md").write_text("line\n" * 20)
    (tmp_path / "gone.md").write_text("bye\n")
    (tmp_path / "old-name.md").write_text("".join(f"line {i}\n" for i in range(20)))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path
```

- [ ] **Step 3: Add `tests/fake_jev.py`**

```python
"""A stand-in for TypeSafeClient that records calls and never touches the network."""
from types import SimpleNamespace

from typesafe_sdk import TypeSafeError


class FakeJevClient:
    """Answers every question at `level`, or at `levels[name]` when given.

    Raises TypeSafeError for any call whose state contains `fail_on`.
    """

    def __init__(self, level=3, levels=None, fail_on=None):
        self.level = level
        self.levels = levels or {}
        self.fail_on = fail_on
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def system_one(self, state, questions):
        self.calls.append({
            "state": state,
            "questions": {
                name: {"instructions": q.instructions, "criteria": list(q.criteria)}
                for name, q in questions.items()
            },
        })
        if self.fail_on and self.fail_on in state:
            raise TypeSafeError("fake outage")
        return SimpleNamespace(answers={
            name: _answer(self.levels.get(name, self.level)) for name in questions
        })


def _answer(level):
    return SimpleNamespace(score=float(level), confidence=0.9, probabilities={level: 1.0})
```

- [ ] **Step 4: Add sample fixtures**

`tests/fixtures/sample_doc.md`:

```markdown
# Rate limits reset on every deploy

Deploys restart the API pods, which clears the in-memory counters.

- Users can exceed their hourly quota right after a deploy.
- Fix: move counters to Redis.
```

`tests/fixtures/sample_source.md`:

```markdown
So we noticed that after deploys people sometimes get way more requests than they should, I think it's because the counters live in memory, which is a bit of a historical thing from when we had one pod. Anyway we should probably move them to Redis.
```

- [ ] **Step 5: Capture what the current scorer sends to Jev**

Run from the repo root:

```bash
evals/.venv/bin/python - <<'EOF'
import json, sys
sys.path[:0] = ["evals", "tests"]
import score_with_jev
from fake_jev import FakeJevClient

client = FakeJevClient()
score_with_jev.TypeSafeClient = lambda: client
doc = open("tests/fixtures/sample_doc.md").read()
source = open("tests/fixtures/sample_source.md").read()
score_with_jev.score_texts({"clean-mode-pr__with__0": doc}, {"clean-mode-pr": source})
with open("tests/fixtures/jev_calls_before_refactor.json", "w") as f:
    json.dump(client.calls, f, indent=2)
    f.write("\n")
print(len(client.calls), "calls captured")
EOF
```

Expected: `2 calls captured` (one `document_only`, one `with_source`). Open the JSON and confirm the second state contains both the sample source and the sample doc.

- [ ] **Step 6: Commit**

```bash
git add pytest.ini evals/requirements-dev.txt tests/
git commit -m "Add test setup and snapshot of the questions sent to Jev"
```

### Task 2: `jev_core` module

**Files:**
- Create: `evals/jev_core.py`
- Test: `tests/test_jev_core.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_jev_core.py`:

```python
import json
from pathlib import Path

import pytest

import jev_core
from fake_jev import FakeJevClient

FIXTURES = Path(__file__).with_name("fixtures")
SAMPLE_DOC = (FIXTURES / "sample_doc.md").read_text()
SAMPLE_SOURCE = (FIXTURES / "sample_source.md").read_text()
CALLS_BEFORE_REFACTOR = json.loads((FIXTURES / "jev_calls_before_refactor.json").read_text())


def test_asks_jev_exactly_what_the_eval_scorer_asked_before_the_refactor():
    client = FakeJevClient()
    jev_core.score_text(client, jev_core.load_config(), SAMPLE_DOC, source=SAMPLE_SOURCE)
    assert client.calls == CALLS_BEFORE_REFACTOR


def test_states_filter_asks_only_the_chosen_rubric_group():
    client = FakeJevClient()
    raw = jev_core.score_text(
        client, jev_core.load_config(), SAMPLE_DOC, source=SAMPLE_SOURCE,
        states={jev_core.DOCUMENT_ONLY},
    )
    assert len(client.calls) == 1
    assert "padding" in raw
    assert "requirements_retained" not in raw


def test_source_rubrics_are_skipped_without_a_source():
    client = FakeJevClient()
    raw = jev_core.score_text(client, jev_core.load_config(), SAMPLE_DOC)
    assert len(client.calls) == 1
    assert "requirements_retained" not in raw


def test_composite_is_the_mean_of_its_normalized_factors():
    client = FakeJevClient(levels={"padding": 3, "economy": 0})
    raw = jev_core.score_text(
        client, jev_core.load_config(), SAMPLE_DOC, states={jev_core.DOCUMENT_ONLY}
    )
    assert raw["concision"]["score"] == pytest.approx(0.5)


def test_unknown_state_is_a_config_error(tmp_path):
    path = tmp_path / "dimensions.json"
    path.write_text(json.dumps({
        "dimensions": {"x": {"state": "nope", "instructions": "i", "criteria": ["a", "b"]}},
        "report_dimensions": ["x"],
    }))
    with pytest.raises(jev_core.ConfigError, match="unknown state"):
        jev_core.load_config(path)


def test_report_dimension_with_no_rubric_is_a_config_error(tmp_path):
    path = tmp_path / "dimensions.json"
    path.write_text(json.dumps({
        "dimensions": {"x": {"instructions": "i", "criteria": ["a", "b"]}},
        "report_dimensions": ["x", "missing"],
    }))
    with pytest.raises(jev_core.ConfigError, match="missing"):
        jev_core.load_config(path)


def test_state_of_a_composite_is_its_factors_state():
    assert jev_core.load_config().state_of("concision") == jev_core.DOCUMENT_ONLY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `evals/.venv/bin/python -m pytest tests/test_jev_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jev_core'`

- [ ] **Step 3: Write `evals/jev_core.py`**

```python
"""Shared Jev scoring for the clean-mode evals and the clean-mode CI check.

Loads the rubrics in dimensions.json, turns them into Jev Score questions,
asks Jev, and adds the composite rubrics. Raises instead of exiting, so each
caller decides how to fail.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import RetryPolicy, Score, TypeSafeClient, TypeSafeError

DEFAULT_CONFIG_PATH = Path(__file__).with_name("dimensions.json")
DOCUMENT_ONLY = "document_only"

__all__ = [
    "Config", "ConfigError", "DOCUMENT_ONLY", "TypeSafeError",
    "load_config", "make_client", "score_text",
]


class ConfigError(Exception):
    """dimensions.json is missing, unreadable, or inconsistent."""


@dataclass(frozen=True)
class Config:
    # How each rubric group's state is laid out; "{source}" means the group
    # compares the document against the material it was written from.
    state_templates: dict
    # Raw rubric entries from dimensions.json, in file order.
    dimensions: dict
    # A composite is a report row with no question of its own: the mean of
    # its factors, each normalized by its own ladder first.
    composites: dict
    report_dimensions: list

    def state_of(self, name):
        """The rubric group a rubric belongs to. A composite takes its factors' group."""
        if name in self.composites:
            states = {self.state_of(factor) for factor in self.composites[name]}
            return states.pop() if len(states) == 1 else None
        return self.dimensions[name].get("state", DOCUMENT_ONLY)

    def top(self, name):
        """Highest level on a rubric's ladder. Composites are already 0 to 1."""
        if name in self.composites:
            return 1
        return len(self.dimensions[name]["criteria"]) - 1

    def normalized(self, name, score):
        return score / self.top(name)

    def questions_by_state(self, states=None):
        grouped = {}
        for name, entry in self.dimensions.items():
            state = entry.get("state", DOCUMENT_ONLY)
            if states is None or state in states:
                grouped.setdefault(state, {})[name] = Score(
                    instructions=entry["instructions"], criteria=entry["criteria"]
                )
        return grouped


def load_config(path=DEFAULT_CONFIG_PATH):
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ConfigError(f"{path}: {e}") from e

    templates = raw.get("state", {DOCUMENT_ONLY: "{document}"})
    dimensions = raw.get("dimensions") or {}
    for name, entry in dimensions.items():
        state = entry.get("state", DOCUMENT_ONLY)
        if state not in templates:
            raise ConfigError(f"{path}: dimension {name} wants unknown state {state!r}")

    composites = {name: tuple(factors) for name, factors in raw.get("composites", {}).items()}
    for name, factors in composites.items():
        unknown = [f for f in factors if f not in dimensions]
        if unknown:
            raise ConfigError(f"{path}: composite {name} names unknown rubrics: {', '.join(unknown)}")

    report = list(raw.get("report_dimensions", []))
    missing = [d for d in report if d not in dimensions and d not in composites]
    if missing:
        raise ConfigError(f"{path}: report_dimensions names nothing: {', '.join(missing)}")

    return Config(templates, dimensions, composites, report)


def make_client(retries=None):
    """A Jev client. retries=None keeps the SDK's default; 0 turns retries off."""
    if retries is None:
        return TypeSafeClient()
    return TypeSafeClient(retry=RetryPolicy(max_retries=retries))


def score_text(client, config, text, source=None, states=None):
    """Score one document: {rubric: {"score", "confidence", "probabilities"}}.

    Rubric groups that need source material are skipped when source is None.
    Composites are added when all their factors were scored; they carry no
    probabilities because they have no ladder of their own.
    """
    raw = {}
    for state, questions in config.questions_by_state(states).items():
        template = config.state_templates[state]
        if "{source}" in template and source is None:
            continue
        response = client.system_one(
            state=template.format(document=text, source=source or ""),
            questions=questions,
        )
        raw.update({
            name: {
                "score": answer.score,
                "confidence": answer.confidence,
                "probabilities": {str(k): v for k, v in answer.probabilities.items()},
            }
            for name, answer in response.answers.items()
        })
    for name, factors in config.composites.items():
        if all(factor in raw for factor in factors):
            parts = [config.normalized(f, raw[f]["score"]) for f in factors]
            confidences = [raw[f]["confidence"] for f in factors]
            raw[name] = {
                "score": sum(parts) / len(parts),
                "confidence": sum(confidences) / len(confidences),
            }
    return raw
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `evals/.venv/bin/python -m pytest tests/test_jev_core.py -v`
Expected: 7 passed.

If the snapshot test fails here, diff `client.calls` against the fixture. The first difference shows what the refactor changed; fix `jev_core`, not the fixture.

Later, an intended edit to `dimensions.json` will also break this snapshot. Then regenerate it: rerun the Task 1, Step 5 script with the last three scoring lines replaced by `jev_core.score_text(client, jev_core.load_config(), doc, source=source)`. Add that as a comment at the top of `tests/test_jev_core.py`.

- [ ] **Step 5: Commit**

```bash
git add evals/jev_core.py tests/test_jev_core.py
git commit -m "Add jev_core, the shared Jev scoring module"
```

### Task 3: Point the eval scorer at `jev_core`

**Files:**
- Modify: `evals/score_with_jev.py:32-83` (imports and config block), `evals/score_with_jev.py:219-251` (`score_texts`)
- Modify: `evals/requirements.txt`
- Test: `tests/test_score_with_jev.py`

- [ ] **Step 1: Write the failing test**

`tests/test_score_with_jev.py`:

```python
import json
from pathlib import Path

import jev_core
import score_with_jev
from fake_jev import FakeJevClient

FIXTURES = Path(__file__).with_name("fixtures")


def test_eval_scorer_still_asks_jev_the_same_questions(monkeypatch):
    client = FakeJevClient()
    monkeypatch.setattr(jev_core, "make_client", lambda retries=None: client)
    score_with_jev.score_texts(
        {"clean-mode-pr__with__0": (FIXTURES / "sample_doc.md").read_text()},
        {"clean-mode-pr": (FIXTURES / "sample_source.md").read_text()},
    )
    assert client.calls == json.loads((FIXTURES / "jev_calls_before_refactor.json").read_text())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY evals/.venv/bin/python -m pytest tests/test_score_with_jev.py -v`
Expected: FAIL with `TypeSafeError` about a missing API key, since the scorer still builds its own `TypeSafeClient`. Unsetting the key keeps this from making a paid Jev call.

- [ ] **Step 3: Replace the import and config block**

In `evals/score_with_jev.py`, replace everything from `try:\n    from typesafe_sdk import Score, TypeSafeClient` (line 32) through the `_missing` check ending at line 83 with:

```python
try:
    import jev_core
except ImportError:
    sys.exit("typesafe-sdk is not installed. Run: pip install typesafe-sdk")

# The questions live in dimensions.json next to this script and are loaded by
# jev_core, which the clean-mode CI check shares, so both ask Jev identical
# questions. Scannability isn't one snap judgment: it depends on independent
# factors, so each gets its own atomic question per Jev's guidance, combined
# by jev_core.score_text. The composite is the MEAN of its factors: a min()
# was tried first and collapsed the composite to section_scannability alone
# (uniformly the lowest factor for both arms), masking the other factors.
#
# Some questions need the source material the document was written from, which
# means a second Jev call against a different state. They are kept as separate
# calls on purpose: the sources are deliberately unedited prose, and a judge
# that has just read one anchors on it when scoring the document's register.
try:
    CONFIG = jev_core.load_config()
except jev_core.ConfigError as e:
    sys.exit(str(e))
COMPOSITES = CONFIG.composites
REPORT_DIMENSIONS = CONFIG.report_dimensions

# A Jev score is a position on the dimension's own criteria ladder, so its
# range is set by how many levels that dimension defines: 0-2 for a 3-level
# question, 0-4 for a 5-level one. Raw scores stay on their native ladder
# everywhere (--out keeps them, so a score still maps onto its criterion
# text); the report divides by the dimension's top level and prints a 0-1
# fraction, so columns built from different ladders are comparable and a
# delta between two of them carries no unit to misread. A composite is
# already 0-1, so its top level is 1.
DIMENSION_TOP = {name: CONFIG.top(name) for name in [*CONFIG.dimensions, *CONFIG.composites]}
```

- [ ] **Step 4: Replace `score_texts`**

```python
def score_texts(texts, sources=None):
    sources = sources or {}
    skipped = set()
    scored = {}
    with jev_core.make_client() as client:
        for key, text in texts.items():
            case = key.rsplit("__", 2)[0]
            if case not in sources:
                skipped.add(case)
            scored[key] = jev_core.score_text(client, CONFIG, text, source=sources.get(case))
    for case in sorted(skipped):
        print(f"warning: no source found for {case}; its with_source dimensions were not scored",
              file=sys.stderr)
    return scored
```

- [ ] **Step 5: Check nothing else used the removed names**

Run: `grep -n "DIMENSIONS_FILE\|DIMENSIONS_BY_STATE\|STATE_TEMPLATES\|\b_config\b\|TypeSafeClient\|\bDIMENSIONS\b" evals/score_with_jev.py`
Expected: no output.

- [ ] **Step 6: Pin dependencies**

`evals/requirements.txt`:

```
typesafe-sdk==0.7.2
pyyaml==6.0.3
```

- [ ] **Step 7: Run all tests and a smoke check**

Run: `evals/.venv/bin/python -m pytest -v && evals/.venv/bin/python evals/score_with_jev.py --help | head -3`
Expected: all tests pass; the help text prints.

- [ ] **Step 8: Commit**

```bash
git add evals/score_with_jev.py evals/requirements.txt tests/test_score_with_jev.py
git commit -m "Score evals through jev_core and pin eval dependencies"
```

---

## Chunk 2: The CI command

### Task 4: Collect changed docs

**Files:**
- Create: `ci/collect.py`
- Test: `tests/test_collect.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_collect.py`:

```python
from collect import ChangedDoc, changed_docs, matches, select
from conftest import git


def test_reports_added_modified_and_edited_renames_but_not_deletions(repo):
    (repo / "keep.md").write_text("line\n" * 20 + "more\n" * 4)
    (repo / "new.md").write_text("a\nb\nc\n")
    (repo / "gone.md").unlink()
    git(repo, "mv", "old-name.md", "new-name.md")
    renamed = repo / "new-name.md"
    renamed.write_text(renamed.read_text() + "edit\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")

    docs = sorted(changed_docs("main~1", cwd=repo), key=lambda d: d.path)

    assert docs == [
        ChangedDoc("keep.md", 4),
        ChangedDoc("new-name.md", 1),
        ChangedDoc("new.md", 3),
    ]


def test_double_star_pattern_also_matches_root_files():
    assert matches("README.md", ["**/*.md"])
    assert matches("docs/a/b.md", ["**/*.md"])
    assert not matches("docs/page.mdx", ["**/*.md"])
    assert matches("docs/page.mdx", ["**/*.md", "**/*.mdx"])


def test_select_ranks_by_lines_changed_and_applies_limits(tmp_path):
    for name, size in [("a.md", 10), ("b.md", 10), ("c.md", 10), ("huge.md", 500), ("typo.md", 10)]:
        (tmp_path / name).write_text("x" * size)
    docs = [
        ChangedDoc("a.md", 5),
        ChangedDoc("b.md", 50),
        ChangedDoc("c.md", 20),
        ChangedDoc("huge.md", 40),
        ChangedDoc("typo.md", 1),
        ChangedDoc("notes.txt", 99),
    ]

    picked = select(docs, ["**/*.md"], min_lines=3, max_files=3, max_chars=100, root=tmp_path)

    assert [path for path, _ in picked.to_score] == ["b.md", "c.md"]
    assert picked.too_large == ["huge.md"]
    assert picked.over_limit == ["a.md"]
    assert picked.to_score[0][1] == "x" * 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `evals/.venv/bin/python -m pytest tests/test_collect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collect'`

- [ ] **Step 3: Write `ci/collect.py`**

```python
"""Find the Markdown docs a pull request changed and choose which to score."""
import fnmatch
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChangedDoc:
    path: str
    lines_changed: int  # additions plus deletions


@dataclass(frozen=True)
class Selection:
    to_score: list = field(default_factory=list)  # (path, text) pairs
    too_large: list = field(default_factory=list)  # paths over max_chars
    over_limit: list = field(default_factory=list)  # paths past max_files


def changed_docs(base, head="HEAD", cwd="."):
    """Added, modified, and renamed files between the merge base and head.

    Deleted files are left out. A rename with no edits reports 0 lines changed.
    """
    result = subprocess.run(
        ["git", "diff", "--numstat", "-z", "-M", "--diff-filter=AMR", f"{base}...{head}"],
        cwd=cwd, check=True, capture_output=True, text=True,
    )
    return parse_numstat(result.stdout)


def parse_numstat(output):
    """Parse `git diff --numstat -z`.

    Each record is "added<TAB>deleted<TAB>path<NUL>". For a rename the path is
    empty and the old and new paths follow as two more NUL-ended fields.
    Binary files report "-" for both counts and are skipped.
    """
    fields = output.split("\0")
    docs = []
    i = 0
    while i < len(fields) and fields[i]:
        added, deleted, path = fields[i].split("\t", 2)
        if path:
            i += 1
        else:
            path = fields[i + 2]
            i += 3
        if added != "-":
            docs.append(ChangedDoc(path, int(added) + int(deleted)))
    return docs


def matches(path, patterns):
    """fnmatch, except a leading "**/" also matches files at the repo root."""
    return any(
        fnmatch.fnmatch(path, p) or (p.startswith("**/") and fnmatch.fnmatch(path, p[3:]))
        for p in patterns
    )


def select(docs, patterns, min_lines, max_files, max_chars, root="."):
    """Keep matching docs with enough changes, most-changed first, within the limits.

    Oversized docs count toward max_files, so the comment lists every doc the
    limit let through, scored or not.
    """
    wanted = [d for d in docs if matches(d.path, patterns) and d.lines_changed >= min_lines]
    wanted.sort(key=lambda d: -d.lines_changed)
    to_score, too_large = [], []
    for doc in wanted[:max_files]:
        text = (Path(root) / doc.path).read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            too_large.append(doc.path)
        else:
            to_score.append((doc.path, text))
    return Selection(to_score, too_large, [d.path for d in wanted[max_files:]])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `evals/.venv/bin/python -m pytest tests/test_collect.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add ci/collect.py tests/test_collect.py
git commit -m "Add changed-doc collection for the clean-mode CI check"
```

### Task 5: Render the comment

**Files:**
- Create: `ci/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:

```python
import pytest

import jev_core
from fake_jev import FakeJevClient
from render import MARKER, ItemResult, ci_rubrics, overall, render, weakest

CONFIG = jev_core.load_config()


def scores(level=3, levels=None):
    client = FakeJevClient(level=level, levels=levels)
    return jev_core.score_text(client, CONFIG, "doc", states={jev_core.DOCUMENT_ONLY})


def test_ci_rubrics_are_the_report_rows_that_need_no_source():
    assert ci_rubrics(CONFIG) == [
        "core_info_first", "title_names_the_outcome", "scannability",
        "structure_not_bolded", "plain_language", "concision",
    ]


def test_overall_is_the_mean_of_the_ci_rubrics():
    assert overall(CONFIG, scores()) == pytest.approx(1.0)
    # padding at 0 halves concision; the other five stay at 1
    assert overall(CONFIG, scores(levels={"padding": 0})) == pytest.approx(5.5 / 6)


def test_weakest_expands_composites_and_breaks_ties_by_file_order():
    # heading_clarity and economy tie at 1/3; heading_clarity is listed first in dimensions.json
    raw = scores(levels={"economy": 1, "padding": 0, "heading_clarity": 1})
    assert [name for name, _, _ in weakest(CONFIG, raw)] == ["padding", "heading_clarity", "economy"]


def test_weakest_shows_the_level_jev_found_most_likely():
    name, score, text = weakest(CONFIG, scores(levels={"padding": 1}))[0]
    assert name == "padding"
    assert score == pytest.approx(1 / 3)
    assert text == CONFIG.dimensions["padding"]["criteria"][1]


def test_render_lists_scored_and_unscored_items():
    md = render(
        CONFIG,
        [ItemResult("PR description", scores()), ItemResult("`a.md`", None, "could not score")],
        too_large=["big.md"], over_limit=["extra.md"], max_chars=30000, max_files=10,
    )
    assert md.startswith(MARKER)
    assert "whole file" in md
    assert "| PR description | 1.00 |" in md
    assert "- `a.md`: could not score" in md
    assert "- `big.md`: over 30,000 characters" in md
    assert "- `extra.md`: over the 10-file limit" in md


def test_render_says_so_when_nothing_changed():
    assert "No changed Markdown" in render(CONFIG, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `evals/.venv/bin/python -m pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'render'`

- [ ] **Step 3: Write `ci/render.py`**

```python
"""Turn Jev scores into the Markdown summary posted on the pull request."""
from dataclasses import dataclass

import jev_core

MARKER = "<!-- clean-mode-check -->"
GUIDE_URL = (
    "https://github.com/Meridian-Labss/galaxy-pocock-skills/blob/main/"
    "skills/productivity/clean-mode/SKILL.md"
)
WEAKEST_COUNT = 3


@dataclass(frozen=True)
class ItemResult:
    label: str  # "PR description" or a file path in backticks
    raw: dict | None  # jev_core.score_text output; None when not scored
    note: str = ""  # why it was not scored


def ci_rubrics(config):
    """Report rows that judge a document on its own, in report order."""
    return [d for d in config.report_dimensions if config.state_of(d) == jev_core.DOCUMENT_ONLY]


def overall(config, raw):
    rubrics = ci_rubrics(config)
    return sum(config.normalized(d, raw[d]["score"]) for d in rubrics) / len(rubrics)


def level_text(config, name, answer):
    """Criterion text for the level Jev found most likely."""
    probabilities = answer["probabilities"]
    level = int(max(probabilities, key=probabilities.get))
    return config.dimensions[name]["criteria"][level]


def weakest(config, raw, count=WEAKEST_COUNT):
    """Lowest-scoring single rubrics as (name, 0-1 score, level text).

    Composites are replaced by their factors, since only single rubrics have
    level text. Ties go to the rubric listed first in dimensions.json.
    """
    file_order = list(config.dimensions)
    single = [f for d in ci_rubrics(config) for f in config.composites.get(d, (d,))]
    single.sort(key=lambda n: (config.normalized(n, raw[n]["score"]), file_order.index(n)))
    return [
        (n, config.normalized(n, raw[n]["score"]), level_text(config, n, raw[n]))
        for n in single[:count]
    ]


def render(config, results, too_large=(), over_limit=(), max_chars=0, max_files=0):
    lines = [
        MARKER,
        "## Clean-mode check",
        "",
        "Advisory only. Each file is scored as a whole file, not just this PR's changes. "
        f"Scores run from 0 to 1. See the [clean-mode guide]({GUIDE_URL}).",
        "",
    ]
    scored = [r for r in results if r.raw is not None]
    if scored:
        lines += ["| Item | Score |", "|---|---|"]
        lines += [f"| {r.label} | {overall(config, r.raw):.2f} |" for r in scored]
        lines.append("")
        for r in scored:
            lines += [f"### {r.label}: {overall(config, r.raw):.2f}", ""]
            lines += [f"- `{n}` ({s:.2f}): {text}" for n, s, text in weakest(config, r.raw)]
            lines.append("")

    unscored = [(r.label, r.note) for r in results if r.raw is None]
    unscored += [(f"`{p}`", f"over {max_chars:,} characters") for p in too_large]
    unscored += [(f"`{p}`", f"over the {max_files}-file limit") for p in over_limit]
    if unscored:
        lines += ["### Not scored", ""]
        lines += [f"- {label}: {note}" for label, note in unscored]
        lines.append("")

    if not scored and not unscored:
        lines += ["No changed Markdown to score.", ""]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `evals/.venv/bin/python -m pytest tests/test_render.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add ci/render.py tests/test_render.py
git commit -m "Render clean-mode CI scores as a PR comment"
```

### Task 6: Post the comment

**Files:**
- Create: `ci/post_comment.py`
- Test: `tests/test_post_comment.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_post_comment.py`:

```python
from post_comment import upsert_comment

MARKER = "<!-- m -->"
ISSUES = "https://api.github.com/repos/o/r/issues"


class FakeGitHub:
    """Serves comment pages for GET and records every request."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url, body))
        if method == "GET":
            page = int(url.rsplit("page=", 1)[1])
            return self.pages[page - 1] if page <= len(self.pages) else []
        return {}


def test_updates_the_marked_comment_even_on_a_later_page():
    github = FakeGitHub([[{"id": 1, "body": "hi"}], [{"id": 7, "body": f"{MARKER}\nold"}]])
    upsert_comment("o/r", 5, "new", "token", MARKER, request=github)
    assert github.calls[-1] == ("PATCH", f"{ISSUES}/comments/7", {"body": "new"})


def test_creates_a_comment_when_none_is_marked():
    github = FakeGitHub([[{"id": 1, "body": None}]])
    upsert_comment("o/r", 5, "new", "token", MARKER, request=github)
    assert github.calls[-1] == ("POST", f"{ISSUES}/5/comments", {"body": "new"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `evals/.venv/bin/python -m pytest tests/test_post_comment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'post_comment'`

- [ ] **Step 3: Write `ci/post_comment.py`**

```python
"""Create or update the single clean-mode comment on a pull request."""
import json
import urllib.request

API_URL = "https://api.github.com"
PAGE_SIZE = 100


def github_request(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def upsert_comment(repo, pr_number, body, token, marker, request=github_request):
    """Edit the comment containing `marker`, or post a new one if none does."""
    issues = f"{API_URL}/repos/{repo}/issues"
    existing = None
    page = 1
    while existing is None:
        comments = request("GET", f"{issues}/{pr_number}/comments?per_page={PAGE_SIZE}&page={page}", token)
        if not comments:
            break
        existing = next((c for c in comments if marker in (c.get("body") or "")), None)
        page += 1
    if existing:
        request("PATCH", f"{issues}/comments/{existing['id']}", token, {"body": body})
    else:
        request("POST", f"{issues}/{pr_number}/comments", token, {"body": body})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `evals/.venv/bin/python -m pytest tests/test_post_comment.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add ci/post_comment.py tests/test_post_comment.py
git commit -m "Post or update the clean-mode PR comment"
```

### Task 7: CLI entry point

**Files:**
- Create: `ci/clean_mode_check.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
import json
import subprocess

import pytest

import clean_mode_check
from conftest import git
from fake_jev import FakeJevClient
from render import MARKER


@pytest.fixture
def pr(repo, tmp_path_factory, monkeypatch):
    """A PR that edits keep.md and adds new.md, with GitHub Actions env set."""
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    (repo / "keep.md").write_text("line\n" * 20 + "more\n" * 4)
    (repo / "new.md").write_text("# New\n\nalpha\nbeta\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")

    out = tmp_path_factory.mktemp("gh")
    event = out / "event.json"
    event.write_text(json.dumps({"pull_request": {
        "number": 5, "title": "Fix limits", "body": "Explains the fix.", "base": {"sha": base},
    }}))
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out / "summary.md"))
    return {"event": event, "summary": out / "summary.md"}


class RecordingPost:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, repo, number, body, token, marker):
        self.calls.append((repo, number, body, marker))
        if self.error:
            raise self.error


def run(pr, client, post, extra=()):
    return clean_mode_check.main(
        ["--event-path", str(pr["event"]), "--post", *extra], client=client, post=post
    )


def test_scores_docs_and_pr_then_posts_one_comment(pr):
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert len(client.calls) == 3  # PR description, keep.md, new.md
    assert "# Fix limits\n\nExplains the fix." in client.calls[0]["state"]
    (repo, number, body, marker), = post.calls
    assert (repo, number, marker) == ("o/r", 5, MARKER)
    assert "| PR description |" in body and "`keep.md`" in body
    assert pr["summary"].read_text().strip() == body.strip()


def test_missing_api_key_skips_without_posting(pr, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert client.calls == [] and post.calls == []


def test_one_failed_jev_call_marks_only_that_item(pr):
    client, post = FakeJevClient(fail_on="alpha"), RecordingPost()
    assert run(pr, client, post) == 0
    body = post.calls[0][2]
    assert "- `new.md`: could not score" in body
    assert "| `keep.md` |" in body


def test_empty_pr_body_is_reported_not_scored(pr):
    event = json.loads(pr["event"].read_text())
    event["pull_request"]["body"] = None
    pr["event"].write_text(json.dumps(event))
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert len(client.calls) == 2
    assert "- PR description: no description" in post.calls[0][2]


def test_a_failed_post_still_exits_zero(pr):
    client, post = FakeJevClient(), RecordingPost(error=OSError("403"))
    assert run(pr, client, post) == 0
    assert pr["summary"].exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `evals/.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'clean_mode_check'`

- [ ] **Step 3: Write `ci/clean_mode_check.py`**

```python
#!/usr/bin/env python3
"""Score the prose in a pull request against clean-mode with Jev.

Advisory: weak prose or an outage at Jev or GitHub never fails the run.
Bugs in this tool or in dimensions.json do.

    python ci/clean_mode_check.py --base main --pr-title "..." --pr-body-file body.md

In GitHub Actions, --event-path (default $GITHUB_EVENT_PATH) supplies the
base commit, PR title, body, and number, and --post updates the PR comment.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import jev_core  # noqa: E402
from collect import changed_docs, select  # noqa: E402
from post_comment import upsert_comment  # noqa: E402
from render import MARKER, ItemResult, render  # noqa: E402

PR_LABEL = "PR description"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="base commit or branch; defaults to the PR's base commit from --event-path")
    parser.add_argument("--pr-title", help="overrides the title from --event-path")
    parser.add_argument("--pr-body-file", help="overrides the body from --event-path")
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--include", default="**/*.md", help="comma-separated globs of files to score")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--max-chars", type=int, default=30000)
    parser.add_argument("--min-lines", type=int, default=3)
    parser.add_argument("--post", action="store_true", help="create or update the PR comment")
    return parser.parse_args(argv)


def read_pr(args):
    """(base, title, body, number), from the event payload unless flags override."""
    pr = {}
    if args.event_path and Path(args.event_path).exists():
        pr = json.loads(Path(args.event_path).read_text()).get("pull_request", {})
    base = args.base or pr.get("base", {}).get("sha")
    title = args.pr_title if args.pr_title is not None else pr.get("title", "")
    body = Path(args.pr_body_file).read_text() if args.pr_body_file else (pr.get("body") or "")
    return base, title, body, pr.get("number")


def score_items(client, config, items):
    """Score (label, text) pairs. A failed Jev call marks only its own item."""
    results = []
    for label, text in items:
        try:
            raw = jev_core.score_text(client, config, text, states={jev_core.DOCUMENT_ONLY})
            results.append(ItemResult(label, raw))
        except jev_core.TypeSafeError as e:
            print(f"::warning::Jev could not score {label}: {e}")
            results.append(ItemResult(label, None, "could not score"))
    return results


def main(argv=None, client=None, post=upsert_comment):
    args = parse_args(argv)
    config = jev_core.load_config()
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("::notice::TYPESAFE_API_KEY is not set (normal for PRs from forks); skipping the clean-mode check")
        return 0

    base, title, body, number = read_pr(args)
    if not base:
        print("::notice::no base commit (pass --base or run on a pull_request event); skipping the clean-mode check")
        return 0
    patterns = [p.strip() for p in args.include.split(",") if p.strip()]
    selection = select(changed_docs(base), patterns, args.min_lines, args.max_files, args.max_chars)

    items = [(f"`{path}`", text) for path, text in selection.to_score]
    unscored = []
    if body.strip():
        items.insert(0, (PR_LABEL, f"# {title}\n\n{body}"))
    else:
        unscored.append(ItemResult(PR_LABEL, None, "no description"))

    with client or jev_core.make_client(retries=0) as jev:
        results = score_items(jev, config, items) + unscored

    markdown = render(config, results, selection.too_large, selection.over_limit, args.max_chars, args.max_files)
    print(markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(markdown + "\n")
    if args.post:
        try:
            post(os.environ["GITHUB_REPOSITORY"], number, markdown, os.environ["GITHUB_TOKEN"], MARKER)
        except (OSError, KeyError, ValueError) as e:  # HTTP and network errors are OSErrors; bad JSON is ValueError
            print(f"::warning::could not post the PR comment: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `evals/.venv/bin/python -m pytest -v`
Expected: all tests pass (the 5 new ones plus every earlier one).

- [ ] **Step 5: Try it locally against this repo**

Run: `evals/.venv/bin/python ci/clean_mode_check.py --base main --pr-title "Test" --pr-body-file README.md`
Expected without `TYPESAFE_API_KEY`: the "skipping" notice and exit 0. With a key: a Markdown summary covering the docs changed on this branch.

- [ ] **Step 6: Commit**

```bash
git add ci/clean_mode_check.py tests/test_cli.py
git commit -m "Add the clean-mode CI command"
```

---

## Chunk 3: Action and workflows

### Task 8: Composite action

**Files:**
- Create: `.github/actions/clean-mode-check/action.yml`
- Create: `.github/actions/clean-mode-check/README.md`

- [ ] **Step 1: Write `action.yml`**

Inputs reach the shell through `env`, never `${{ }}` inside `run`, so input values cannot inject shell code.

```yaml
name: Clean-mode check
description: Score a pull request's prose against clean-mode with Jev and post one advisory comment.
inputs:
  typesafe-api-key:
    description: TypeSafe API key. If empty, the check skips.
    required: false
    default: ""
  github-token:
    description: Token used to post the PR comment.
    required: false
    default: ${{ github.token }}
  include:
    description: Comma-separated globs of files to score. Add **/*.mdx to opt in.
    required: false
    default: "**/*.md"
  max-files:
    description: Most docs to score, ranked by lines changed.
    required: false
    default: "10"
  max-chars:
    description: Docs longer than this are skipped, not truncated.
    required: false
    default: "30000"
  min-lines:
    description: Docs with fewer lines changed are not scored.
    required: false
    default: "3"
runs:
  using: composite
  steps:
    # update-environment: false leaves the consumer's own Python on PATH
    - id: py
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"
        update-environment: false
    - name: Install dependencies
      shell: bash
      env:
        PYTHON: ${{ steps.py.outputs.python-path }}
      run: |
        "$PYTHON" -m venv "$RUNNER_TEMP/clean-mode-venv"
        "$RUNNER_TEMP/clean-mode-venv/bin/python" -m pip install --quiet -r "$GITHUB_ACTION_PATH/../../../evals/requirements.txt"
    - name: Score prose
      shell: bash
      env:
        TYPESAFE_API_KEY: ${{ inputs.typesafe-api-key }}
        GITHUB_TOKEN: ${{ inputs.github-token }}
        INCLUDE: ${{ inputs.include }}
        MAX_FILES: ${{ inputs.max-files }}
        MAX_CHARS: ${{ inputs.max-chars }}
        MIN_LINES: ${{ inputs.min-lines }}
      run: >
        "$RUNNER_TEMP/clean-mode-venv/bin/python" "$GITHUB_ACTION_PATH/../../../ci/clean_mode_check.py" --post
        --include "$INCLUDE" --max-files "$MAX_FILES"
        --max-chars "$MAX_CHARS" --min-lines "$MIN_LINES"
```

- [ ] **Step 2: Write the README**

Run the `clean-mode` skill first. Content to cover, in this order:

1. One line: what it does and that it is advisory.
2. The usage YAML from the spec's "How a repo uses it" section, with `<org>` replaced by `Meridian-Labss`. Keep `contents: read` in its `permissions` block: listing any permission sets the rest to none, and checkout needs read access on private repos.
3. The inputs table from the spec.
4. Fork PRs are not scored (no secrets), and scores cover whole files.
5. Versioning: consumers pin `@v1`; maintainers move the tag with `git tag -f v1 && git push -f origin v1` after a release.
6. It only runs on `pull_request` events; on any other trigger it posts a notice and does nothing.

Then add one line to the top-level `README.md` pointing to this README (the global rule keeps the README in sync with major features). Place it near the end, outside the skill lists, so the skill-listing rules in `CLAUDE.md` are unaffected.

- [ ] **Step 3: Commit**

```bash
git add .github/actions/clean-mode-check/ README.md
git commit -m "Add the clean-mode-check composite action"
```

### Task 9: Test workflow

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: Test

on:
  pull_request:
    paths:
      - "ci/**"
      - "tests/**"
      - "pytest.ini"
      - "evals/jev_core.py"
      - "evals/score_with_jev.py"
      - "evals/dimensions.json"
      - "evals/requirements*.txt"
      - ".github/actions/**"
      - ".github/workflows/test.yml"

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -r evals/requirements-dev.txt
      - run: python -m pytest -v
```

- [ ] **Step 2: Run the same steps locally on Python 3.12, if available**

Run: `d=$(mktemp -d) && python3.12 -m venv "$d" && "$d/bin/pip" install -q -r evals/requirements-dev.txt && "$d/bin/python" -m pytest -q`
Expected: all tests pass. If `python3.12` is missing, note it and rely on the workflow run in Task 10.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "Run the clean-mode CI tests on pull requests"
```

### Task 10: End-to-end check on this repo

Needs the user: pushing, a `TYPESAFE_API_KEY` repo secret, and opening PRs are outward-facing. Ask before each.

**Files:**
- Create: `.github/workflows/clean-mode-check.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: Clean-mode check

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
      - uses: ./.github/actions/clean-mode-check
        with:
          typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/clean-mode-check.yml
git commit -m "Run the clean-mode check on this repo's pull requests"
```

- [ ] **Step 3: Ask the user to add the secret and approve pushing**

The user adds `TYPESAFE_API_KEY` under the repo's Actions secrets. With approval, push the branch and open a draft PR.

- [ ] **Step 4: Add a throwaway test commit**

On a separate branch from `feat/clean-mode-ci-check`, add:
- `scratch/padded.md`: a doc full of hedging, restatement, and bold field labels
- `scratch/clean.md`: the same facts written per clean-mode

Open a draft PR. Check:
- the Test and Clean-mode check workflows both pass
- exactly one comment appears, scoring the PR description and both docs
- `scratch/padded.md` scores lower than `scratch/clean.md`

- [ ] **Step 5: Push a second commit to the same PR**

Check that the existing comment is updated and no second comment appears.

- [ ] **Step 6: Close the throwaway PR without merging and delete its branch**

Ask the user whether to keep `.github/workflows/clean-mode-check.yml` on this repo permanently.
