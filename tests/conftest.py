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
