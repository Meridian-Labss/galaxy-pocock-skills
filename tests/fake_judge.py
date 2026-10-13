"""A stand-in judge that records calls and never touches the network."""
from judges import Answer, JudgeError


class FakeJudge:
    """Answers every rubric at `level`, or at `levels[name]` when given.

    Raises JudgeError for any call whose text contains `fail_on`.
    """

    name = "fake"
    model = "fake-model"

    def __init__(self, level=3, levels=None, fail_on=None, error_message="fake outage"):
        self.level = level
        self.levels = levels or {}
        self.fail_on = fail_on
        self.error_message = error_message
        self.calls = []

    def score(self, text, rubrics):
        self.calls.append({"text": text, "rubrics": rubrics})
        if self.fail_on and self.fail_on in text:
            raise JudgeError(self.error_message)
        return {name: _answer(self.levels.get(name, self.level)) for name in rubrics}

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _answer(level):
    return Answer(score=float(level), confidence=0.9, probabilities={level: 1.0})
