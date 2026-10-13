import json

import pytest
from typesafe_sdk import SystemOneResponse, TypeSafeError

from judges import Answer, JudgeError, Rubric
from judges import typesafe as typesafe_judge

RUBRICS = {
    "padding": Rubric(instructions="Is it padded?", levels=["very", "a little", "not at all"]),
    "economy": Rubric(instructions="Is it economical?", levels=["no", "yes"]),
}


def response(answers):
    """A real SystemOneResponse, parsed from the JSON TypeSafe sends back."""
    return SystemOneResponse.model_validate_json(json.dumps({
        "model": "jev-latest",
        "usage": {"input_tokens": 10, "output_tokens": 2},
        "answers": answers,
    }))


def score_answer(score, probabilities):
    return {
        "type": "score", "score": score, "confidence": 0.8,
        "legend": {k: f"level {k}" for k in probabilities},
        "probabilities": probabilities,
    }


class StandInClient:
    """Records system_one calls and returns a canned response or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.closed = False

    def system_one(self, state, questions):
        self.calls.append({"state": state, "questions": questions})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self):
        self.closed = True


def both_answered():
    return response({
        "padding": score_answer(1.5, {"0": 0.1, "1": 0.3, "2": 0.6}),
        "economy": score_answer(0.9, {"0": 0.1, "1": 0.9}),
    })


def test_sends_each_rubric_as_a_score_question_with_the_text_as_state():
    client = StandInClient(both_answered())
    typesafe_judge.TypeSafeJudge(client=client).score("the doc", RUBRICS)
    (call,) = client.calls
    assert call["state"] == "the doc"
    assert set(call["questions"]) == {"padding", "economy"}
    padding = call["questions"]["padding"]
    assert padding.type == "score"
    assert padding.instructions == "Is it padded?"
    assert list(padding.criteria) == ["very", "a little", "not at all"]


def test_maps_answers_to_judge_answers():
    answers = typesafe_judge.TypeSafeJudge(client=StandInClient(both_answered())).score("doc", RUBRICS)
    assert answers["padding"] == Answer(score=1.5, confidence=0.8, probabilities={0: 0.1, 1: 0.3, 2: 0.6})
    assert answers["economy"].probabilities == {0: 0.1, 1: 0.9}


def test_a_missing_answer_raises_judge_error():
    partial = response({"padding": score_answer(1.0, {"0": 0.5, "1": 0.5})})
    with pytest.raises(JudgeError, match="economy"):
        typesafe_judge.TypeSafeJudge(client=StandInClient(partial)).score("doc", RUBRICS)


def test_typesafe_errors_become_judge_errors():
    client = StandInClient(TypeSafeError("rate limited"))
    with pytest.raises(JudgeError, match="rate limited"):
        typesafe_judge.TypeSafeJudge(client=client).score("doc", RUBRICS)


def test_retries_zero_turns_retries_off(monkeypatch):
    seen = {}
    monkeypatch.setattr(typesafe_judge, "TypeSafeClient", lambda **kwargs: seen.update(kwargs))
    typesafe_judge.TypeSafeJudge(retries=0)
    assert seen["retry"].max_retries == 0


def test_default_retries_leave_the_client_default(monkeypatch):
    seen = {}
    monkeypatch.setattr(typesafe_judge, "TypeSafeClient", lambda **kwargs: seen.update(kwargs))
    typesafe_judge.TypeSafeJudge()
    assert seen == {}


def test_a_missing_key_raises_judge_error_naming_it(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JudgeError, match="TYPESAFE_API_KEY"):
        typesafe_judge.TypeSafeJudge()


def test_closing_the_judge_closes_the_client(monkeypatch):
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    client = StandInClient(both_answered())
    with typesafe_judge.TypeSafeJudge(client=client) as judge:
        assert judge.name == "typesafe"
        assert judge.model == "jev-latest"
    assert client.closed
