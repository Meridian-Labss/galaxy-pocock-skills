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
