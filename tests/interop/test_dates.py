from interop.dates import day_distance, parse_flexible_date


def test_parses_iso_format() -> None:
    parsed = parse_flexible_date("2026-03-15")
    assert parsed is not None
    assert parsed.isoformat() == "2026-03-15"


def test_parses_us_format() -> None:
    parsed = parse_flexible_date("3/15/2026")
    assert parsed is not None
    assert parsed.isoformat() == "2026-03-15"


def test_parses_text_format() -> None:
    parsed = parse_flexible_date("March 15, 2026")
    assert parsed is not None
    assert parsed.isoformat() == "2026-03-15"


def test_malformed_date_returns_none() -> None:
    assert parse_flexible_date("15/45/2026") is None


def test_garbage_returns_none() -> None:
    assert parse_flexible_date("not a date") is None


def test_day_distance_zero_for_same_date_different_formats() -> None:
    assert day_distance("2026-03-15", "3/15/2026") == 0


def test_day_distance_computes_correctly() -> None:
    assert day_distance("2026-03-15", "2026-03-20") == 5


def test_day_distance_none_when_either_side_unparseable() -> None:
    assert day_distance("2026-03-15", "garbage") is None
    assert day_distance("garbage", "2026-03-15") is None
