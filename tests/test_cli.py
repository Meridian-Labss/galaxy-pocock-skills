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
