"""Shared Jev scoring for the clean-mode evals and the clean-mode CI check.

Loads the rubrics in dimensions.json, turns them into Jev Score questions,
asks Jev, and adds the composite rubrics. Raises instead of exiting, so each
caller decides how to fail.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import RetryPolicy, Score, TypeSafeClient, TypeSafeError

DEFAULT_CONFIG_PATH = Path(__file__).with_name("dimensions.json")
DOCUMENT_ONLY = "document_only"

__all__ = [
    "Config", "ConfigError", "DOCUMENT_ONLY", "TypeSafeError",
    "load_config", "make_client", "score_text",
]


class ConfigError(Exception):
    """dimensions.json is missing, unreadable, or inconsistent."""


@dataclass(frozen=True)
class Config:
    # How each rubric group's state is laid out; "{source}" means the group
    # compares the document against the material it was written from.
    state_templates: dict
    # Raw rubric entries from dimensions.json, in file order.
    dimensions: dict
    # A composite is a report row with no question of its own: the mean of
    # its factors, each normalized by its own ladder first.
    composites: dict
    report_dimensions: list

    def state_of(self, name):
        """The rubric group a rubric belongs to. A composite takes its factors' group."""
        if name in self.composites:
            states = {self.state_of(factor) for factor in self.composites[name]}
            return states.pop() if len(states) == 1 else None
        return self.dimensions[name].get("state", DOCUMENT_ONLY)

    def top(self, name):
        """Highest level on a rubric's ladder. Composites are already 0 to 1."""
        if name in self.composites:
            return 1
        return len(self.dimensions[name]["criteria"]) - 1

    def normalized(self, name, score):
        return score / self.top(name)

    def questions_by_state(self, states=None):
        grouped = {}
        for name, entry in self.dimensions.items():
            state = entry.get("state", DOCUMENT_ONLY)
            if states is None or state in states:
                grouped.setdefault(state, {})[name] = Score(
                    instructions=entry["instructions"], criteria=entry["criteria"]
                )
        return grouped


def load_config(path=DEFAULT_CONFIG_PATH):
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ConfigError(f"{path}: {e}") from e

    templates = raw.get("state", {DOCUMENT_ONLY: "{document}"})
    dimensions = raw.get("dimensions") or {}
    for name, entry in dimensions.items():
        state = entry.get("state", DOCUMENT_ONLY)
        if state not in templates:
            raise ConfigError(f"{path}: dimension {name} wants unknown state {state!r}")

    composites = {name: tuple(factors) for name, factors in raw.get("composites", {}).items()}
    for name, factors in composites.items():
        unknown = [f for f in factors if f not in dimensions]
        if unknown:
            raise ConfigError(f"{path}: composite {name} names unknown rubrics: {', '.join(unknown)}")

    report = list(raw.get("report_dimensions", []))
    missing = [d for d in report if d not in dimensions and d not in composites]
    if missing:
        raise ConfigError(f"{path}: report_dimensions names nothing: {', '.join(missing)}")

    return Config(templates, dimensions, composites, report)


def make_client(retries=None):
    """A Jev client. retries=None keeps the SDK's default; 0 turns retries off."""
    if retries is None:
        return TypeSafeClient()
    return TypeSafeClient(retry=RetryPolicy(max_retries=retries))


def score_text(client, config, text, source=None, states=None):
    """Score one document: {rubric: {"score", "confidence", "probabilities"}}.

    Rubric groups that need source material are skipped when source is None.
    Composites are added when all their factors were scored; they carry no
    probabilities because they have no ladder of their own.
    """
    raw = {}
    for state, questions in config.questions_by_state(states).items():
        template = config.state_templates[state]
        if "{source}" in template and source is None:
            continue
        response = client.system_one(
            state=template.format(document=text, source=source or ""),
            questions=questions,
        )
        raw.update({
            name: {
                "score": answer.score,
                "confidence": answer.confidence,
                "probabilities": {str(k): v for k, v in answer.probabilities.items()},
            }
            for name, answer in response.answers.items()
        })
    for name, factors in config.composites.items():
        if all(factor in raw for factor in factors):
            parts = [config.normalized(f, raw[f]["score"]) for f in factors]
            confidences = [raw[f]["confidence"] for f in factors]
            raw[name] = {
                "score": sum(parts) / len(parts),
                "confidence": sum(confidences) / len(confidences),
            }
    return raw
