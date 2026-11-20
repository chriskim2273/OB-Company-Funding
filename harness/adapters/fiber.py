"""Fiber company search by exact domain. Fiber takes the API key in the request body."""
from __future__ import annotations

from typing import Any

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter, first_value, latest_round


class Fiber(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.post("https://api.fiber.ai/v1/company-search",
                         json={"apiKey": self.key("FIBER_API_KEY"), "searchParams": {
                             "exactCompanyV2": {"anyOf": [{"identifier": "domain", "domain": company.domain}]}}})

    def not_found(self, body: dict[str, Any]) -> str | None:
        output = body.get("output") or {}
        return None if output.get("data") else (output.get("message") or "no company match")

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        item = ((body.get("output") or {}).get("data") or [{}])[0]
        rounds = item.get("full_funding_rounds") or item.get("funding_rounds") or []
        result = latest_round(rounds, date_key="round_date", stage_key="round_type", amount_key="round_raised_usd")
        if not result["latest_stage"]:
            result["latest_stage"] = first_value(item.get("latest_funding_consensus")) or item.get("funding_stage")
        result["total_raised"] = first_value(item.get("total_funding_consensus"))
        return result

    def cost(self, response: Response) -> tuple[float | None, str | None]:
        charged = ((response.body or {}).get("chargeInfo") or {}).get("creditsCharged") if isinstance(response.body, dict) else None
        return (float(charged), "credit") if isinstance(charged, (int, float)) else (None, None)


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Fiber:
    return Fiber(setup, spec, env)
