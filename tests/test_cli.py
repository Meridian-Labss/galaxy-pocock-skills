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


def test_unreachable_base_is_a_setup_error(pr, capsys):
    client, post = FakeJevClient(), RecordingPost()
    code = clean_mode_check.main(
        ["--event-path", str(pr["event"]), "--base", "0" * 40, "--post"], client=client, post=post
    )
    assert code == 1
    assert "::error::could not diff" in capsys.readouterr().out
    assert client.calls == [] and post.calls == []


def test_local_mode_uses_flags_and_does_not_post(pr, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    body_file = tmp_path / "body.md"
    body_file.write_text("Local body.")
    client, post = FakeJevClient(), RecordingPost()
    code = clean_mode_check.main(
        ["--base", "main~1", "--pr-title", "Local", "--pr-body-file", str(body_file)],
        client=client, post=post,
    )
    assert code == 0
    assert "# Local\n\nLocal body." in client.calls[0]["state"]
    assert post.calls == []
    assert "| PR description |" in capsys.readouterr().out


def test_whitespace_only_body_is_reported_as_no_description(pr):
    event = json.loads(pr["event"].read_text())
    event["pull_request"]["body"] = "  \n "
    pr["event"].write_text(json.dumps(event))
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert len(client.calls) == 2
    assert "- PR description: no description" in post.calls[0][2]


def test_empty_title_scores_the_body_alone(pr):
    event = json.loads(pr["event"].read_text())
    event["pull_request"]["title"] = None
    pr["event"].write_text(json.dumps(event))
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert client.calls[0]["state"] == "Explains the fix."


def test_missing_pr_number_skips_posting(pr):
    event = json.loads(pr["event"].read_text())
    del event["pull_request"]["number"]
    pr["event"].write_text(json.dumps(event))
    client, post = FakeJevClient(), RecordingPost()
    assert run(pr, client, post) == 0
    assert post.calls == []


def test_escape_command_encodes_workflow_command_characters():
    assert clean_mode_check.escape_command("a%b\r\nc") == "a%25b%0D%0Ac"


def test_diffs_the_pr_head_not_the_checked_out_commit(pr, repo, capsys):
    base = json.loads(pr["event"].read_text())["pull_request"]["base"]["sha"]
    # Rebuild from the base: a PR branch with pr-doc.md, and a main-only doc.
    git(repo, "checkout", "-q", "-b", "pr-branch", base)
    (repo / "pr-doc.md").write_text("# PR\n\nalpha\nbeta\ngamma\n")
    git(repo, "add", "pr-doc.md")
    git(repo, "commit", "-qm", "pr change")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    git(repo, "checkout", "-q", "-b", "other-main", base)
    (repo / "main-only.md").write_text("# Main\n\nmain one\nmain two\nmain three\n")
    git(repo, "add", "main-only.md")
    git(repo, "commit", "-qm", "main only")
    # Stale checkout: HEAD is the main-only commit, but the PR file is in the tree.
    git(repo, "checkout", "pr-branch", "--", "pr-doc.md")

    event = json.loads(pr["event"].read_text())
    event["pull_request"]["head"] = {"sha": head}
    pr["event"].write_text(json.dumps(event))
    client, post = FakeJevClient(), RecordingPost()

    assert run(pr, client, post) == 0

    states = "\n".join(call["state"] for call in client.calls)
    assert "alpha" in states and "main one" not in states
    body = post.calls[0][2]
    assert "`pr-doc.md`" in body and "main-only.md" not in body


def test_failure_text_with_newlines_cannot_inject_workflow_commands(pr, capsys):
    client = FakeJevClient(fail_on="alpha", error_message="boom\n::error::injected")
    assert run(pr, client, RecordingPost()) == 0
    lines = capsys.readouterr().out.splitlines()
    warning = next(l for l in lines if l.startswith("::warning::"))
    assert not any(l.startswith("::error::") for l in lines)
    assert "boom%0A::error::injected" in warning
