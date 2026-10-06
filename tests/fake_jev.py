"""A stand-in for TypeSafeClient that records calls and never touches the network."""
from types import SimpleNamespace

from typesafe_sdk import TypeSafeError


class FakeJevClient:
    """Answers every question at `level`, or at `levels[name]` when given.

    Raises TypeSafeError for any call whose state contains `fail_on`.
    """

    def __init__(self, level=3, levels=None, fail_on=None):
        self.level = level
        self.levels = levels or {}
        self.fail_on = fail_on
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def system_one(self, state, questions):
        self.calls.append({
            "state": state,
            "questions": {
                name: {"instructions": q.instructions, "criteria": list(q.criteria)}
                for name, q in questions.items()
            },
        })
        if self.fail_on and self.fail_on in state:
            raise TypeSafeError("fake outage")
        return SimpleNamespace(answers={
            name: _answer(self.levels.get(name, self.level)) for name in questions
        })


def _answer(level):
    return SimpleNamespace(score=float(level), confidence=0.9, probabilities={level: 1.0})
