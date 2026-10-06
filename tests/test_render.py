import pytest

import jev_core
from fake_jev import FakeJevClient
from render import MARKER, ItemResult, ci_rubrics, overall, render, weakest

CONFIG = jev_core.load_config()


def scores(level=3, levels=None):
    client = FakeJevClient(level=level, levels=levels)
    return jev_core.score_text(client, CONFIG, "doc", states={jev_core.DOCUMENT_ONLY})


def test_ci_rubrics_are_the_report_rows_that_need_no_source():
    assert ci_rubrics(CONFIG) == [
        "core_info_first", "title_names_the_outcome", "scannability",
        "structure_not_bolded", "plain_language", "concision",
    ]


def test_overall_is_the_mean_of_the_ci_rubrics():
    assert overall(CONFIG, scores()) == pytest.approx(1.0)
    # padding at 0 halves concision; the other five stay at 1
    assert overall(CONFIG, scores(levels={"padding": 0})) == pytest.approx(5.5 / 6)


def test_weakest_expands_composites_and_breaks_ties_by_file_order():
    # heading_clarity and economy tie at 1/3; heading_clarity is listed first in dimensions.json
    raw = scores(levels={"economy": 1, "padding": 0, "heading_clarity": 1})
    assert [name for name, _, _ in weakest(CONFIG, raw)] == ["padding", "heading_clarity", "economy"]


def test_weakest_shows_the_level_jev_found_most_likely():
    name, score, text = weakest(CONFIG, scores(levels={"padding": 1}))[0]
    assert name == "padding"
    assert score == pytest.approx(1 / 3)
    assert text == CONFIG.dimensions["padding"]["criteria"][1]


def test_render_lists_scored_and_unscored_items():
    md = render(
        CONFIG,
        [ItemResult("PR description", scores()), ItemResult("`a.md`", None, "could not score")],
        too_large=["big.md"], over_limit=["extra.md"], max_chars=30000, max_files=10,
    )
    assert md.startswith(MARKER)
    assert "whole file" in md
    assert "| PR description | 1.00 |" in md
    assert "- `a.md`: could not score" in md
    assert "- `big.md`: over 30,000 characters" in md
    assert "- `extra.md`: over the 10-file limit" in md


def test_render_says_so_when_nothing_changed():
    assert "No changed Markdown" in render(CONFIG, [])
