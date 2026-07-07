import pytest

from interop.normalize import name_similarity, normalize_name


def test_legal_suffix_and_abbreviation_normalize_the_same() -> None:
    assert normalize_name("Blue Ridge Eqpt LLC") == normalize_name("Blue Ridge Equipment")


def test_case_and_punctuation_are_ignored() -> None:
    assert normalize_name("Summit & Supply, Inc.") == normalize_name("summit supply")


def test_identical_names_have_similarity_one() -> None:
    assert name_similarity("Blue Ridge Equipment", "Blue Ridge Equipment") == pytest.approx(1.0)


def test_unrelated_names_have_low_similarity() -> None:
    assert name_similarity("Blue Ridge Equipment", "Coastal Crane Services") < 0.4


def test_abbreviated_variant_scores_high() -> None:
    score = name_similarity("Blue Ridge Eqpt", "Blue Ridge Equipment")
    assert score > 0.85


def test_truncated_variant_scores_lower_than_abbreviated() -> None:
    truncated = name_similarity("Blue Ridge", "Blue Ridge Equipment Rental Partners")
    abbreviated = name_similarity(
        "Blue Ridge Eqpt Rental Partners", "Blue Ridge Equipment Rental Partners"
    )
    assert truncated < abbreviated
