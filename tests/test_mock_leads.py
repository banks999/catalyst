import pytest

from mock_leads import COMPANY_POOL, KNOWN_STATES, _apply_filters, mock_answer
from tables import parse_markdown_table_to_df


def names(q):
    return {r[0] for r in _apply_filters(q)}


def pool(state=None, size=None):
    return {c[0] for c in COMPANY_POOL
            if (state is None or c[4] == state) and (size is None or c[5] == size)}


def test_pool_is_well_formed():
    assert len({c[0] for c in COMPANY_POOL}) == len(COMPANY_POOL)  # unique names
    assert all(len(c) == 6 and all(c) for c in COMPANY_POOL)
    assert all(c[4] in KNOWN_STATES for c in COMPANY_POOL)
    assert all(c[5] in {"large", "medium", "small"} for c in COMPANY_POOL)


# --- the three documented demo queries -------------------------------------
def test_demo_gujarat_query():
    assert names("companies that buy maleic anhydride near Gujarat") == pool("Gujarat")


def test_demo_large_query():
    assert names("large industrial solvent manufacturers") == pool(size="large")


def test_unfiltered_query_returns_everything():
    assert names("resin makers") == pool()


# --- location ---------------------------------------------------------------
@pytest.mark.parametrize("q", ["near Gujarat", "in Ahmedabad", "near gidc", "near surat"])
def test_gujarat_aliases(q):
    assert names(q) == pool("Gujarat")


def test_multiple_states_are_a_union():
    assert names("Gujarat or Maharashtra") == pool("Gujarat") | pool("Maharashtra")


def test_unknown_location_is_reported_not_ignored():
    for q in ["companies near Kerala", "small companies in Kerala", "near kerala"]:
        assert _apply_filters(q) == []
        assert "No sample data for Kerala" in mock_answer(q)


def test_country_names_do_not_filter():
    assert names("resin makers in India") == pool()


def test_near_me_is_not_a_place():
    assert names("resin makers near me") == pool()


# --- size -------------------------------------------------------------------
def test_size_words():
    assert names("MSME resin makers") == pool(size="small")
    assert names("medium companies") == pool(size="medium")


def test_size_and_location_combine():
    assert names("large companies in Gujarat") == pool("Gujarat", "large")


# --- exclusions -------------------------------------------------------------
def test_exclude_by_name():
    assert "Bhansali Engineering Polymers Ltd" not in names("styrene buyers exclude Bhansali")
    assert len(names("styrene buyers exclude Bhansali")) == len(COMPANY_POOL) - 1


def test_exclusion_stops_before_following_clause():
    # Used to swallow "styrenix near gujarat" as one name and exclude nothing.
    got = names("resin makers exclude Styrenix near Gujarat")
    assert got == pool("Gujarat") - {"Styrenix Performance Materials Ltd"}


def test_multiple_exclusions():
    got = names("exclude Styrenix and Crest, near Gujarat")
    assert got == {"Josh Resins"}


@pytest.mark.parametrize("q", ["exclude Gujarat companies", "resin makers, not Gujarat"])
def test_exclude_by_location(q):
    assert names(q) == pool() - pool("Gujarat")


def test_exclusion_does_not_leak_into_inclusion():
    assert names("not large companies") != pool(size="large")


def test_not_inside_a_word_is_not_an_exclusion():
    assert names("cannot find anything") == pool()


def test_exclusion_is_case_insensitive():
    assert names("EXCLUDE JOSH") == pool() - {"Josh Resins"}


def test_impossible_combo_gives_friendly_row():
    out = mock_answer("large companies in Gujarat, exclude Styrenix")
    assert "No matching companies found" in out


# --- output shape -----------------------------------------------------------
def test_answer_is_a_parseable_four_column_table():
    df = parse_markdown_table_to_df(mock_answer("resin makers"))
    assert list(df.columns) == ["Company Name", "Contact Number", "Email ID", "Product Made"]
    assert len(df) == len(COMPANY_POOL)


def test_never_raises_on_odd_input():
    for q in ["", None, "   ", "|||", "exclude", "near", "in", "🤷", "a" * 10_000]:
        assert mock_answer(q).startswith("| Company Name")
