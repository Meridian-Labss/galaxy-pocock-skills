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
