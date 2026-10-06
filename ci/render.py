"""Turn Jev scores into the Markdown summary posted on the pull request."""
from dataclasses import dataclass

import jev_core

MARKER = "<!-- clean-mode-check -->"
GUIDE_URL = (
    "https://github.com/Meridian-Labss/galaxy-pocock-skills/blob/main/"
    "skills/productivity/clean-mode/SKILL.md"
)
WEAKEST_COUNT = 3
MAX_UNSCORED_LISTED = 20


@dataclass(frozen=True)
class ItemResult:
    label: str  # "PR description" or a file path in backticks
    raw: dict | None  # jev_core.score_text output; None when not scored
    note: str = ""  # why it was not scored


def escape_cell(text):
    return text.replace("|", "\\|")


def ci_rubrics(config):
    """Report rows that judge a document on its own, in report order."""
    return [d for d in config.report_dimensions if config.state_of(d) == jev_core.DOCUMENT_ONLY]


def overall(config, raw):
    rubrics = ci_rubrics(config)
    return sum(config.normalized(d, raw[d]["score"]) for d in rubrics) / len(rubrics)


def level_text(config, name, answer):
    """Criterion text for the level Jev found most likely."""
    probabilities = answer["probabilities"]
    level = int(max(probabilities, key=probabilities.get))
    return config.dimensions[name]["criteria"][level]


def weakest(config, raw, count=WEAKEST_COUNT):
    """Lowest-scoring single rubrics as (name, 0-1 score, level text).

    Composites are replaced by their factors, since only single rubrics have
    level text. Ties go to the rubric listed first in dimensions.json.
    """
    file_order = list(config.dimensions)
    single = [f for d in ci_rubrics(config) for f in config.composites.get(d, (d,))]
    single.sort(key=lambda n: (config.normalized(n, raw[n]["score"]), file_order.index(n)))
    return [
        (n, config.normalized(n, raw[n]["score"]), level_text(config, n, raw[n]))
        for n in single[:count]
    ]


def render(config, results, too_large=(), over_limit=(), max_chars=0, max_files=0):
    lines = [
        MARKER,
        "## Clean-mode check",
        "",
        "Advisory only. Each file is scored as a whole file, not just this PR's changes. "
        f"Scores run from 0 to 1. See the [clean-mode guide]({GUIDE_URL}).",
        "",
    ]
    scored = [r for r in results if r.raw is not None]
    if scored:
        lines += ["| Item | Score |", "|---|---|"]
        lines += [f"| {escape_cell(r.label)} | {overall(config, r.raw):.2f} |" for r in scored]
        lines.append("")
        for r in scored:
            lines += [f"### {r.label}: {overall(config, r.raw):.2f}", ""]
            lines += [f"- `{n}` ({s:.2f}): {text}" for n, s, text in weakest(config, r.raw)]
            lines.append("")

    unscored = [(r.label, r.note) for r in results if r.raw is None]
    unscored += [(f"`{p}`", f"over {max_chars:,} characters") for p in too_large]
    unscored += [(f"`{p}`", f"over the {max_files}-file limit") for p in over_limit]
    if unscored:
        lines += ["### Not scored", ""]
        lines += [f"- {label}: {note}" for label, note in unscored[:MAX_UNSCORED_LISTED]]
        if len(unscored) > MAX_UNSCORED_LISTED:
            lines.append(f"- ...and {len(unscored) - MAX_UNSCORED_LISTED} more")
        lines.append("")

    if not scored and not unscored:
        lines += ["No changed Markdown to score.", ""]
    return "\n".join(lines)
