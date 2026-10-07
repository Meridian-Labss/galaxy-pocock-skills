#!/usr/bin/env python3
"""Score the prose in a pull request against clean-mode with Jev.

Advisory: weak prose or an outage at Jev or GitHub never fails the run.
Bugs in this tool or in dimensions.json do.

    python ci/clean_mode_check.py --base main --pr-title "..." --pr-body-file body.md

In GitHub Actions, --event-path (default $GITHUB_EVENT_PATH) supplies the
base commit, PR title, body, and number, and --post updates the PR comment.
"""
import argparse
import http.client
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import jev_core  # noqa: E402
from collect import changed_docs, select  # noqa: E402
from post_comment import upsert_comment  # noqa: E402
from render import MARKER, ItemResult, render  # noqa: E402

PR_LABEL = "PR description"
# Jev accepts at most 32k tokens for the document plus its longest question
# (about 400 tokens today). At a worst case of 2.5 characters per token
# (code-heavy Markdown), 75,000 characters is about 30k tokens, leaving room.
DEFAULT_MAX_CHARS = 75000


def escape_command(text):
    """Escape text for a GitHub workflow command message."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="base commit or branch; defaults to the PR's base commit from --event-path")
    parser.add_argument("--pr-title", help="overrides the title from --event-path")
    parser.add_argument("--pr-body-file", help="overrides the body from --event-path")
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--include", default="**/*.md", help="comma-separated globs of files to score")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--min-lines", type=int, default=3)
    parser.add_argument("--post", action="store_true", help="create or update the PR comment")
    return parser.parse_args(argv)


def read_pr(args):
    """(base, head, title, body, number), from the event payload unless flags override."""
    pr = {}
    if args.event_path and Path(args.event_path).exists():
        pr = json.loads(Path(args.event_path).read_text(encoding="utf-8")).get("pull_request", {})
    base = args.base or pr.get("base", {}).get("sha")
    head = pr.get("head", {}).get("sha") or "HEAD"
    title = args.pr_title if args.pr_title is not None else (pr.get("title") or "")
    body = (
        Path(args.pr_body_file).read_text(encoding="utf-8")
        if args.pr_body_file else (pr.get("body") or "")
    )
    return base, head, title, body, pr.get("number")


def score_items(client, config, items):
    """Score (label, text) pairs. A failed Jev call marks only its own item."""
    results = []
    for label, text in items:
        try:
            raw = jev_core.score_text(client, config, text, states={jev_core.DOCUMENT_ONLY})
            results.append(ItemResult(label, raw))
        except jev_core.TypeSafeError as e:
            print(f"::warning::{escape_command(f'Jev could not score {label}: {e}')}")
            results.append(ItemResult(label, None, "could not score"))
    return results


def main(argv=None, client=None, post=upsert_comment):
    args = parse_args(argv)
    config = jev_core.load_config()
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("::notice::TYPESAFE_API_KEY is not set (normal for PRs from forks); skipping the clean-mode check")
        return 0

    base, head, title, body, number = read_pr(args)
    if not base:
        print("::notice::no base commit (pass --base or run on a pull_request event); skipping the clean-mode check")
        return 0
    patterns = [p.strip() for p in args.include.split(",") if p.strip()]
    try:
        docs = changed_docs(base, head)
    except subprocess.CalledProcessError as e:
        detail = escape_command(f"could not diff {base}...{head}; check out with fetch-depth: 0. {e.stderr}".strip())
        print(f"::error::{detail}")
        return 1
    selection = select(docs, patterns, args.min_lines, args.max_files, args.max_chars)

    items = [(f"`{path}`", text) for path, text in selection.to_score]
    unscored = []
    if body.strip():
        items.insert(0, (PR_LABEL, f"# {title}\n\n{body}" if title else body))
    else:
        unscored.append(ItemResult(PR_LABEL, None, "no description"))

    with client or jev_core.make_client(retries=0) as jev:
        results = score_items(jev, config, items) + unscored

    markdown = render(config, results, selection.too_large, selection.over_limit, args.max_chars, args.max_files)
    print(markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
    if args.post and number is None:
        print("::notice::no pull request number; not posting the PR comment")
    elif args.post:
        try:
            post(os.environ["GITHUB_REPOSITORY"], number, markdown, os.environ["GITHUB_TOKEN"], MARKER)
        except (OSError, KeyError, ValueError, http.client.HTTPException) as e:  # HTTP and network errors are OSErrors; bad JSON is ValueError; truncated responses raise HTTPException
            print(f"::warning::{escape_command(f'could not post the PR comment: {e}')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
