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


def test_ignores_comments_that_only_mention_the_marker():
    github = FakeGitHub([[{"id": 1, "body": f"quoting {MARKER} here"}]])
    upsert_comment("o/r", 5, "new", "token", MARKER, request=github)
    assert github.calls[-1][0] == "POST"


def test_creates_a_comment_when_none_is_marked():
    github = FakeGitHub([[{"id": 1, "body": None}]])
    upsert_comment("o/r", 5, "new", "token", MARKER, request=github)
    assert github.calls[-1] == ("POST", f"{ISSUES}/5/comments", {"body": "new"})
