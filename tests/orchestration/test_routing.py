import pytest

from orchestration.routing import RoutingTable


def test_load_default_routing_table_from_repo_yaml() -> None:
    table = RoutingTable.load()
    assert table.model_for("ambiguous_discrepancy") == "claude-haiku-4-5"
    assert table.model_for("disagreement_writeup") == "claude-sonnet-5"
    assert table.model_for("disagreement_writeup_escalated") == "claude-opus-4-8"


def test_tier_for_resolves_route_to_tier_name() -> None:
    table = RoutingTable.load()
    assert table.tier_for("ambiguous_discrepancy") == "cheap"
    assert table.tier_for("disagreement_writeup_escalated") == "expensive"


def test_unknown_route_raises() -> None:
    table = RoutingTable.load()
    with pytest.raises(ValueError, match="no route configured"):
        table.model_for("some_route_that_does_not_exist")


def test_route_pointing_at_unconfigured_tier_raises() -> None:
    table = RoutingTable(tiers={"cheap": "claude-haiku-4-5"}, routes={"x": "nonexistent_tier"})
    with pytest.raises(ValueError, match="unconfigured tier"):
        table.model_for("x")
