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
