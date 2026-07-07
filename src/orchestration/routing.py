"""Deterministic model-tier routing table, loaded from routing.yaml.

A YAML file rather than a hardcoded dict deliberately: this table is a
config change, not a code change, when a new model ships or a route's
tier assignment needs to move — the same reasoning behind the vendor
mixture-of-experts strategy in src/adapters, applied at the tier level
instead of the provider level.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

_DEFAULT_PATH = Path(__file__).resolve().parent / "routing.yaml"


class RoutingTable(BaseModel):
    tiers: dict[str, str]
    routes: dict[str, str]

    def model_for(self, route: str) -> str:
        """Resolve a named route to a concrete model ID."""
        tier_name = self.routes.get(route)
        if tier_name is None:
            raise ValueError(f"no route configured for {route!r}")
        model_id = self.tiers.get(tier_name)
        if model_id is None:
            raise ValueError(f"route {route!r} points at unconfigured tier {tier_name!r}")
        return model_id

    def tier_for(self, route: str) -> str:
        """Resolve a named route to its tier name (for cost-report grouping)."""
        tier_name = self.routes.get(route)
        if tier_name is None:
            raise ValueError(f"no route configured for {route!r}")
        return tier_name

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RoutingTable":
        target = Path(path) if path is not None else _DEFAULT_PATH
        with open(target) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
