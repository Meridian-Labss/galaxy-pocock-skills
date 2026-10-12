"""The judging models the scorer can ask, behind one small interface.

A judge scores one text against a set of rubrics. Each provider has an
adapter in this package that keeps its request and answer shapes to itself,
and imports its provider's library only when chosen.
"""
from dataclasses import dataclass
from typing import Protocol

# Each judge reads its own API key from this environment variable.
API_KEY_ENV = {"typesafe": "TYPESAFE_API_KEY", "openai": "OPENAI_API_KEY"}
NAMES = tuple(API_KEY_ENV)


class JudgeError(Exception):
    """The provider failed: network error, rate limit, refusal, or a missing answer."""


@dataclass(frozen=True)
class Rubric:
    instructions: str
    levels: list[str]  # worst to best: the rubric file's `criteria`


@dataclass(frozen=True)
class Answer:
    score: float  # expected level, 0 to len(levels) - 1
    confidence: float
    probabilities: dict[int, float]  # level -> probability


class Judge(Protocol):
    name: str  # "typesafe" or "openai"
    model: str  # for report headers

    def score(self, text: str, rubrics: dict[str, Rubric]) -> dict[str, Answer]: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Judge": ...
    def __exit__(self, *exc) -> None: ...


def make_judge(name, retries=None):
    """A judge by name. retries=None keeps the provider's default; 0 turns retries off."""
    if name == "typesafe":
        from judges.typesafe import TypeSafeJudge
        return TypeSafeJudge(retries=retries)
    raise ValueError(f"unknown judge {name!r}; choose one of: {', '.join(NAMES)}")
