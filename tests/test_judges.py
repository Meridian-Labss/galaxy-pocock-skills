import os
import subprocess
import sys
from pathlib import Path

import pytest

import judges

EVALS = Path(__file__).resolve().parent.parent / "evals"


def test_make_judge_builds_the_typesafe_judge(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    with judges.make_judge("typesafe") as judge:
        assert judge.name == "typesafe"


def test_unknown_judge_lists_the_valid_ones():
    with pytest.raises(ValueError, match="typesafe, openai"):
        judges.make_judge("gemini")


def test_each_judge_names_its_key():
    assert judges.API_KEY_ENV == {"typesafe": "TYPESAFE_API_KEY", "openai": "OPENAI_API_KEY"}


def test_make_judge_builds_the_openai_judge(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with judges.make_judge("openai") as judge:
        assert judge.name == "openai"


def test_choosing_typesafe_does_not_import_openai():
    code = "import sys, judges; judges.make_judge('typesafe'); print('openai' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=EVALS, capture_output=True, text=True, check=True,
        env={**os.environ, "TYPESAFE_API_KEY": "test-key"},
    )
    assert result.stdout.strip() == "False"


def test_choosing_openai_does_not_import_typesafe():
    code = "import sys, judges; judges.make_judge('openai'); print('typesafe_sdk' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=EVALS, capture_output=True, text=True, check=True,
        env={**os.environ, "OPENAI_API_KEY": "test-key"},
    )
    assert result.stdout.strip() == "False"
