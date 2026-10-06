import json
from pathlib import Path

import pytest

import jev_core
from fake_jev import FakeJevClient

FIXTURES = Path(__file__).with_name("fixtures")
SAMPLE_DOC = (FIXTURES / "sample_doc.md").read_text()
SAMPLE_SOURCE = (FIXTURES / "sample_source.md").read_text()


def test_states_filter_asks_only_the_chosen_rubric_group():
    client = FakeJevClient()
    raw = jev_core.score_text(
        client, jev_core.load_config(), SAMPLE_DOC, source=SAMPLE_SOURCE,
        states={jev_core.DOCUMENT_ONLY},
    )
    assert len(client.calls) == 1
    assert "padding" in raw
    assert "requirements_retained" not in raw


def test_source_rubrics_are_skipped_without_a_source():
    client = FakeJevClient()
    raw = jev_core.score_text(client, jev_core.load_config(), SAMPLE_DOC)
    assert len(client.calls) == 1
    assert "requirements_retained" not in raw


def test_composite_is_the_mean_of_its_normalized_factors():
    client = FakeJevClient(levels={"padding": 3, "economy": 0})
    raw = jev_core.score_text(
        client, jev_core.load_config(), SAMPLE_DOC, states={jev_core.DOCUMENT_ONLY}
    )
    assert raw["concision"]["score"] == pytest.approx(0.5)


def test_unknown_state_is_a_config_error(tmp_path):
    path = tmp_path / "dimensions.json"
    path.write_text(json.dumps({
        "dimensions": {"x": {"state": "nope", "instructions": "i", "criteria": ["a", "b"]}},
        "report_dimensions": ["x"],
    }))
    with pytest.raises(jev_core.ConfigError, match="unknown state"):
        jev_core.load_config(path)


def test_report_dimension_with_no_rubric_is_a_config_error(tmp_path):
    path = tmp_path / "dimensions.json"
    path.write_text(json.dumps({
        "dimensions": {"x": {"instructions": "i", "criteria": ["a", "b"]}},
        "report_dimensions": ["x", "missing"],
    }))
    with pytest.raises(jev_core.ConfigError, match="missing"):
        jev_core.load_config(path)


def test_state_of_a_composite_is_its_factors_state():
    assert jev_core.load_config().state_of("concision") == jev_core.DOCUMENT_ONLY
