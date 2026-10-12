import pytest

import judges


def test_make_judge_builds_the_typesafe_judge(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    with judges.make_judge("typesafe") as judge:
        assert judge.name == "typesafe"


def test_unknown_judge_lists_the_valid_ones():
    with pytest.raises(ValueError, match="typesafe, openai"):
        judges.make_judge("gemini")


def test_each_judge_names_its_key():
    assert judges.API_KEY_ENV == {"typesafe": "TYPESAFE_API_KEY", "openai": "OPENAI_API_KEY"}
