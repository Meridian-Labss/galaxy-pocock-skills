import pytest

import scoring
from fake_judge import FakeJudge
from render import MARKER, ItemResult, ci_rubrics, needs_work, overall, rating, render

CONFIG = scoring.load_config()


def scores(level=3, levels=None):
    judge = FakeJudge(level=level, levels=levels)
    return scoring.score_text(judge, CONFIG, "doc", states={scoring.DOCUMENT_ONLY})


def test_ci_rubrics_are_the_report_rows_that_need_no_source():
    assert ci_rubrics(CONFIG) == [
        "core_info_first", "title_names_the_outcome", "scannability",
        "structure_not_bolded", "plain_language", "concision",
    ]


def test_overall_is_the_mean_of_the_ci_rubrics():
    assert overall(CONFIG, scores()) == pytest.approx(1.0)
    # padding at 0 halves concision; the other five stay at 1
    assert overall(CONFIG, scores(levels={"padding": 0})) == pytest.approx(5.5 / 6)


@pytest.mark.parametrize("score, word", [
    (0.0, "Poor"), (0.16, "Poor"), (1 / 6, "Fair"), (0.49, "Fair"),
    (0.5, "Good"), (0.83, "Good"), (0.84, "Excellent"), (1.0, "Excellent"),
])
def test_rating_rounds_to_the_nearest_of_four_levels(score, word):
    assert rating(score) == word


def test_needs_work_lists_only_poor_and_fair_rubrics_by_plain_name():
    # padding Poor, economy Fair, heading_clarity Good: Good is not listed
    raw = scores(levels={"padding": 0, "economy": 1, "heading_clarity": 2})
    assert [(label, word) for label, word, _ in needs_work(CONFIG, raw)] == [
        ("No padding", "Poor"), ("Concise wording", "Fair"),
    ]


def test_needs_work_breaks_ties_by_file_order_and_caps_at_three():
    # all at Fair; file order: title_names_the_outcome, heading_clarity, plain_language, economy
    raw = scores(levels={"economy": 1, "plain_language": 1, "heading_clarity": 1, "title_names_the_outcome": 1})
    assert [label for label, _, _ in needs_work(CONFIG, raw)] == [
        "Clear title", "Clear headings", "Plain language",
    ]


def test_needs_work_carries_the_level_text_the_judge_found_most_likely():
    _, _, text = needs_work(CONFIG, scores(levels={"padding": 1}))[0]
    assert text == CONFIG.dimensions["padding"]["criteria"][1]


def test_render_lists_scored_and_unscored_items():
    md = render(
        CONFIG,
        [ItemResult("PR description", scores()), ItemResult("`a.md`", None, "could not score")],
        too_large=["big.md"], over_limit=["extra.md"], max_chars=30000, max_files=10,
    )
    assert md.startswith(MARKER)
    assert "whole" in md
    assert "| PR description | Excellent | none |" in md
    assert "- `a.md`: could not score" in md
    assert "- `big.md`: over 30,000 characters" in md
    assert "- `extra.md`: over the 10-file limit" in md


def test_render_says_so_when_nothing_changed():
    assert "No changed Markdown" in render(CONFIG, [])


def test_render_escapes_pipes_in_table_labels():
    md = render(CONFIG, [ItemResult("`a|b.md`", scores())])
    assert "| `a\\|b.md` | Excellent |" in md


def test_render_caps_the_not_scored_list():
    paths = [f"f{i}.md" for i in range(25)]
    md = render(CONFIG, [], over_limit=paths, max_files=1)
    assert "- `f19.md`: over the 1-file limit" in md
    assert "`f20.md`" not in md
    assert "- ...and 5 more" in md


def test_table_lists_worst_first_with_ratings_and_no_numbers():
    md = render(CONFIG, [
        ItemResult("`good.md`", scores()),
        ItemResult("`bad.md`", scores(level=1, levels={"padding": 0})),
    ])
    assert md.index("`bad.md`") < md.index("`good.md`")
    assert "| Item | Rating | Needs work |" in md
    assert "| `bad.md` | Fair | No padding (Poor), Core point first (Fair), Clear title (Fair) |" in md
    assert "0." not in md and "1.00" not in md


def test_item_with_nothing_below_good_needs_no_work():
    md = render(CONFIG, [ItemResult("`good.md`", scores(level=2))])
    assert "| `good.md` | Good | none |" in md
    assert "<details>" not in md


def test_each_explanation_appears_once_with_its_rating_and_items():
    padding_text = CONFIG.dimensions["padding"]["criteria"][0]
    md = render(CONFIG, [
        ItemResult("`a.md`", scores(levels={"padding": 0})),
        ItemResult("`b.md`", scores(levels={"padding": 0})),
    ])
    assert md.count(padding_text) == 1
    details = md[md.index("<details>"):md.index("</details>")]
    assert "<summary>Why these ratings</summary>" in details
    assert f"- No padding, Poor: {padding_text} (`a.md`, `b.md`)" in details


def test_rubric_without_a_label_falls_back_to_its_code_name(tmp_path):
    import json
    raw = json.loads(scoring.DEFAULT_CONFIG_PATH.read_text())
    del raw["dimensions"]["padding"]["label"]
    path = tmp_path / "dimensions.json"
    path.write_text(json.dumps(raw))
    config = scoring.load_config(path)
    raw_scores = scoring.score_text(FakeJudge(levels={"padding": 0}), config, "doc", states={scoring.DOCUMENT_ONLY})
    assert ("padding", "Poor") in [(label, word) for label, word, _ in needs_work(config, raw_scores)]


def test_no_per_item_sections():
    md = render(CONFIG, [ItemResult("`a.md`", scores(levels={"padding": 0}))])
    assert "### `a.md`" not in md
