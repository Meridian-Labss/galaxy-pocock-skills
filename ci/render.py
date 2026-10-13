"""Turn judge scores into the Markdown summary posted on the pull request."""
from dataclasses import dataclass

import scoring

MARKER = "<!-- clean-mode-check -->"
GUIDE_URL = (
    "https://github.com/Meridian-Labss/galaxy-pocock-skills/blob/main/"
    "skills/productivity/clean-mode/SKILL.md"
)
NEEDS_WORK_COUNT = 3
# A rubric's four levels, worst to best. A 0-1 score rounds to the nearest one.
RATINGS = ("Poor", "Fair", "Good", "Excellent")
# Ratings listed under "Needs work".
NEEDS_WORK_RATINGS = ("Poor", "Fair")
MAX_UNSCORED_LISTED = 20


@dataclass(frozen=True)
class ItemResult:
    label: str  # "PR description" or a file path in backticks
    raw: dict | None  # scoring.score_text output; None when not scored
    note: str = ""  # why it was not scored


def escape_cell(text):
    return text.replace("|", "\\|")


def ci_rubrics(config):
    """Report rows that judge a document on its own, in report order."""
    return [d for d in config.report_dimensions if config.state_of(d) == scoring.DOCUMENT_ONLY]


def overall(config, raw):
    rubrics = ci_rubrics(config)
    return sum(config.normalized(d, raw[d]["score"]) for d in rubrics) / len(rubrics)


def rating(score):
    """The word for a 0-1 score: the nearest of the four rubric levels."""
    # Round half up: Python's round() sends exact halves to the even level.
    return RATINGS[int(score * (len(RATINGS) - 1) + 0.5)]


def rubric_label(config, name):
    """The rubric's plain name for readers, or its code name if it has none."""
    return config.dimensions[name].get("label", name)


def improvement_tip(config, name, answer):
    """How to raise this rubric's rating.

    Falls back to the level the judge found most likely when the rubric has
    no tip of its own.
    """
    tip = config.dimensions[name].get("advice")
    if tip:
        return tip
    probabilities = answer["probabilities"]
    level = int(max(probabilities, key=probabilities.get))
    return config.dimensions[name]["criteria"][level]


def needs_work(config, raw, count=NEEDS_WORK_COUNT):
    """Single rubrics rated below Good, worst first, as (plain name, rating, improvement tip).

    Composites are replaced by their factors, since only single rubrics have
    level text. Ties go to the rubric listed first in dimensions.json.
    """
    file_order = list(config.dimensions)
    single = [f for d in ci_rubrics(config) for f in config.composites.get(d, (d,))]
    weak = [n for n in single if rating(config.normalized(n, raw[n]["score"])) in NEEDS_WORK_RATINGS]
    weak.sort(key=lambda n: (config.normalized(n, raw[n]["score"]), file_order.index(n)))
    return [
        (rubric_label(config, n), rating(config.normalized(n, raw[n]["score"])), improvement_tip(config, n, raw[n]))
        for n in weak[:count]
    ]


def improvements(config, scored):
    """Each weak rubric's tip once, with the items it applies to and their ratings, worst items first."""
    grouped = {}
    for r in scored:
        for label, word, tip in needs_work(config, r.raw):
            grouped.setdefault((label, tip), []).append((r.label, word))
    return grouped


def render(config, results, too_large=(), over_limit=(), max_chars=0, max_files=0, judge_note=None):
    lines = [
        MARKER,
        "## Clean-mode check",
        "",
        "Advisory only. Each file is rated as a whole, not just this PR's changes, "
        f"from Poor through Fair and Good to Excellent. See the [clean-mode guide]({GUIDE_URL}).",
        "",
    ]
    if judge_note:
        lines += [judge_note, ""]
    scored = sorted((r for r in results if r.raw is not None), key=lambda r: overall(config, r.raw))
    if scored:
        lines += ["| Item | Rating | Needs work |", "|---|---|---|"]
        for r in scored:
            weak = ", ".join(f"{label} ({word})" for label, word, _ in needs_work(config, r.raw)) or "none"
            lines.append(f"| {escape_cell(r.label)} | {rating(overall(config, r.raw))} | {weak} |")
        lines.append("")
        grouped = improvements(config, scored)
        if grouped:
            lines += ["<details><summary>How to improve</summary>", ""]
            lines += [
                f"- {label}: {tip} ({', '.join(f'{item}: {word}' for item, word in items)})"
                for (label, tip), items in grouped.items()
            ]
            lines += ["", "</details>", ""]

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
