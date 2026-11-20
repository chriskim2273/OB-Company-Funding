"""Ocean.io company enrichment, asking only for the funding-round fields in the setup's settings."""
from __future__ import annotations

from typing import Any

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter


class Ocean(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.post("https://api.ocean.io/v2/enrich/company",
                         headers={"X-Api-Token": self.key("OCEAN_API_KEY"), "Accept": "application/json",
                                  "Content-Type": "application/json"},
                         json={"company": {"domain": company.domain}, "fields": list(self.settings["fields"])})

    def not_found(self, body: dict[str, Any]) -> str | None:
        return None if body.get("domain") else "no company"

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        item = body.get("fundingRound") or {}
        return {"latest_stage": item.get("type"), "latest_date": item.get("date"),
                "latest_amount": item.get("moneyRaisedInUsd"), "total_raised": None, "round_count": None}

    def cost(self, response: Response) -> tuple[float | None, str | None]:
        credits = response.body.get("creditsUsed") if isinstance(response.body, dict) else None
        return (float(credits), "credit") if isinstance(credits, (int, float)) else (None, None)


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Ocean:
    return Ocean(setup, spec, env)
