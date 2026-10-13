"""Adapter for TypeSafe's Jev."""
import os

from typesafe_sdk import RetryPolicy, Score, TypeSafeClient, TypeSafeError
from typesafe_sdk.constants import DEFAULT_MODEL, DEFAULT_MODEL_ENV

from judges import Answer, JudgeError


class TypeSafeJudge:
    name = "typesafe"

    def __init__(self, client=None, retries=None):
        if client is None:
            try:
                client = (
                    TypeSafeClient() if retries is None
                    else TypeSafeClient(retry=RetryPolicy(max_retries=retries))
                )
            except TypeSafeError as e:
                raise JudgeError(str(e)) from e
        self._client = client
        # The SDK's own default: TYPESAFE_DEFAULT_MODEL when set, else jev-latest.
        self.model = os.environ.get(DEFAULT_MODEL_ENV, "").strip() or DEFAULT_MODEL

    def score(self, text, rubrics):
        questions = {
            name: Score(instructions=r.instructions, criteria=r.levels)
            for name, r in rubrics.items()
        }
        try:
            response = self._client.system_one(state=text, questions=questions)
        except TypeSafeError as e:
            raise JudgeError(str(e)) from e
        missing = [name for name in rubrics if name not in response.answers]
        if missing:
            raise JudgeError(f"no answer for {', '.join(missing)}")
        return {
            name: Answer(
                score=answer.score,
                confidence=answer.confidence,
                probabilities=dict(answer.probabilities),
            )
            for name, answer in response.answers.items()
            if name in rubrics
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
