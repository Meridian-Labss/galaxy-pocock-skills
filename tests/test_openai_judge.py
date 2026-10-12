from types import SimpleNamespace

import pytest
from openai import OpenAIError
from openai.types.decision import Decision

from judges import Answer, JudgeError, Rubric
from judges import openai as openai_judge

RUBRICS = {
    "padding": Rubric(instructions="Is it padded?", levels=["very", "a little", "not at all"]),
    "economy": Rubric(instructions="Is it economical?", levels=["no", "yes"]),
}


def decision(answers):
    """A real Decision, validated the way the library parses OpenAI's reply."""
    return Decision.model_validate({
        "model": openai_judge.MODEL,
        "usage": {
            "input_tokens": 10, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
            "output_tokens": 2, "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 12,
        },
        "answers": answers,
    })


def score_answer(name, score, probabilities):
    return {
        "type": "score", "name": name, "score": score, "confidence": 0.7,
        "probabilities": [
            {"value": level, "label": f"level {level}", "probability": p}
            for level, p in probabilities.items()
        ],
    }


class StandInClient:
    """Mimics OpenAI's client: records decisions.create calls and returns a canned result or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.closed = False
        self.decisions = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self):
        self.closed = True


def both_answered():
    return decision([
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
        score_answer("economy", 0.9, {0: 0.1, 1: 0.9}),
    ])


def test_sends_every_rubric_as_a_named_score_question_in_one_request():
    client = StandInClient(both_answered())
    openai_judge.OpenAIJudge(client=client).score("the doc", RUBRICS)
    (call,) = client.calls
    assert call["model"] == "gpt-6-luna"
    assert call["input"] == "the doc"
    assert call["questions"] == [
        {
            "type": "score", "name": "padding", "instructions": "Is it padded?",
            "levels": [
                {"label": "level 0", "description": "very"},
                {"label": "level 1", "description": "a little"},
                {"label": "level 2", "description": "not at all"},
            ],
        },
        {
            "type": "score", "name": "economy", "instructions": "Is it economical?",
            "levels": [
                {"label": "level 0", "description": "no"},
                {"label": "level 1", "description": "yes"},
            ],
        },
    ]


def test_matches_answers_by_name_even_out_of_order():
    reversed_order = decision([
        score_answer("economy", 0.9, {0: 0.1, 1: 0.9}),
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
    ])
    answers = openai_judge.OpenAIJudge(client=StandInClient(reversed_order)).score("doc", RUBRICS)
    assert answers["padding"] == Answer(score=1.5, confidence=0.7, probabilities={0: 0.1, 1: 0.3, 2: 0.6})
    assert answers["economy"] == Answer(score=0.9, confidence=0.7, probabilities={0: 0.1, 1: 0.9})


def test_a_refusal_raises_judge_error():
    refused = decision([
        score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6}),
        {"type": "refusal", "name": "economy"},
    ])
    with pytest.raises(JudgeError, match="refused.*economy"):
        openai_judge.OpenAIJudge(client=StandInClient(refused)).score("doc", RUBRICS)


def test_a_missing_answer_raises_judge_error():
    partial = decision([score_answer("padding", 1.5, {0: 0.1, 1: 0.3, 2: 0.6})])
    with pytest.raises(JudgeError, match="no answer for economy"):
        openai_judge.OpenAIJudge(client=StandInClient(partial)).score("doc", RUBRICS)


def test_openai_errors_become_judge_errors():
    client = StandInClient(OpenAIError("rate limited"))
    with pytest.raises(JudgeError, match="rate limited"):
        openai_judge.OpenAIJudge(client=client).score("doc", RUBRICS)


def test_retries_zero_reaches_the_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with openai_judge.OpenAIJudge(retries=0) as judge:
        assert judge._client.max_retries == 0


def test_a_missing_key_raises_judge_error_naming_it(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(JudgeError, match="OPENAI_API_KEY"):
        openai_judge.OpenAIJudge()


def test_closing_the_judge_closes_the_client():
    client = StandInClient(both_answered())
    with openai_judge.OpenAIJudge(client=client) as judge:
        assert (judge.name, judge.model) == ("openai", "gpt-6-luna")
    assert client.closed


@pytest.mark.parametrize("bad_padding", [
    score_answer("padding", 2.5, {1: 0.1, 2: 0.3, 3: 0.6}),  # levels numbered from 1
    score_answer("padding", 3.0, {0: 0.1, 1: 0.3, 2: 0.6}),  # score above the top level
])
def test_answer_outside_the_rubric_ladder_is_a_judge_error(bad_padding):
    reply = decision([bad_padding, score_answer("economy", 1.0, {0: 0.0, 1: 1.0})])
    with pytest.raises(JudgeError, match="padding"):
        openai_judge.OpenAIJudge(client=StandInClient(reply)).score("doc", RUBRICS)


def test_malformed_score_answer_is_a_judge_error():
    # The library parses replies leniently, so a field can arrive missing.
    economy = decision([score_answer("economy", 1.0, {0: 0.0, 1: 1.0})]).answers[0]
    padding = SimpleNamespace(type="score", name="padding", score=1.0, confidence=0.7, probabilities=None)
    reply = SimpleNamespace(answers=[padding, economy])
    with pytest.raises(JudgeError, match="padding"):
        openai_judge.OpenAIJudge(client=StandInClient(reply)).score("doc", RUBRICS)


@pytest.mark.parametrize("probabilities", [
    [SimpleNamespace(value=None, probability=1.0)],
    [SimpleNamespace(value="2", probability=1.0)],
    [SimpleNamespace(value=2, probability=None)],
    [],
])
def test_malformed_probabilities_are_a_judge_error(probabilities):
    economy = decision([score_answer("economy", 1.0, {0: 0.0, 1: 1.0})]).answers[0]
    padding = SimpleNamespace(type="score", name="padding", score=1.0, confidence=0.7, probabilities=probabilities)
    reply = SimpleNamespace(answers=[padding, economy])
    with pytest.raises(JudgeError, match="padding"):
        openai_judge.OpenAIJudge(client=StandInClient(reply)).score("doc", RUBRICS)
