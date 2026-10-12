"""Adapter for OpenAI's Decisions API."""
from openai import OpenAI, OpenAIError

from judges import Answer, JudgeError

# The model OpenAI's Decisions guide names.
MODEL = "gpt-6-luna"


class OpenAIJudge:
    name = "openai"
    model = MODEL

    def __init__(self, client=None, retries=None):
        if client is None:
            try:
                client = OpenAI() if retries is None else OpenAI(max_retries=retries)
            except OpenAIError as e:
                raise JudgeError(str(e)) from e
        self._client = client

    def score(self, text, rubrics):
        questions = [
            {
                "type": "score",
                "name": name,
                "instructions": rubric.instructions,
                "levels": [
                    {"label": f"level {i}", "description": level}
                    for i, level in enumerate(rubric.levels)
                ],
            }
            for name, rubric in rubrics.items()
        ]
        try:
            decision = self._client.decisions.create(model=MODEL, input=text, questions=questions)
        except OpenAIError as e:
            raise JudgeError(str(e)) from e
        by_name = {answer.name: answer for answer in decision.answers}
        answers = {}
        for name in rubrics:
            answer = by_name.get(name)
            if answer is None:
                raise JudgeError(f"no answer for {name}")
            if answer.type == "refusal":
                raise JudgeError(f"OpenAI refused to score {name}")
            if answer.type != "score":
                raise JudgeError(f"expected a score for {name}, got a {answer.type}")
            answers[name] = _to_answer(name, answer, len(rubrics[name].levels))
        return answers

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()



def _to_answer(name, answer, level_count):
    """Map a score answer, rejecting any that falls outside the rubric's levels (0 to level_count - 1)."""
    try:
        probabilities = {p.value: p.probability for p in answer.probabilities}
        score, confidence = float(answer.score), float(answer.confidence)
    except (AttributeError, TypeError, ValueError) as e:
        raise JudgeError(f"malformed answer for {name}: {e}") from e
    top = level_count - 1
    if not 0 <= score <= top or any(not 0 <= level <= top for level in probabilities):
        raise JudgeError(f"answer for {name} falls outside levels 0 to {top}")
    return Answer(score=score, confidence=confidence, probabilities=probabilities)
