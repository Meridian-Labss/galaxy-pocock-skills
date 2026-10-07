"""GitHub API calls: look up a pull request, and create or update its clean-mode comment."""
import json
import urllib.request

API_URL = "https://api.github.com"
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30


def github_request(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read() or b"null")


def fetch_pull_request(repo, number, token, request=github_request):
    """The pull request's details, for events that carry only its number (comments)."""
    return request("GET", f"{API_URL}/repos/{repo}/pulls/{number}", token)


def upsert_comment(repo, pr_number, body, token, marker, request=github_request):
    """Edit the comment containing `marker`, or post a new one if none does."""
    issues = f"{API_URL}/repos/{repo}/issues"
    existing = None
    page = 1
    while existing is None:
        comments = request("GET", f"{issues}/{pr_number}/comments?per_page={PAGE_SIZE}&page={page}", token)
        if not comments:
            break
        existing = next((c for c in comments if (c.get("body") or "").startswith(marker)), None)
        page += 1
    if existing:
        request("PATCH", f"{issues}/comments/{existing['id']}", token, {"body": body})
    else:
        request("POST", f"{issues}/{pr_number}/comments", token, {"body": body})
