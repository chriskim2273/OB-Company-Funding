"""Fundable company funding by domain."""
from __future__ import annotations

from typing import Any

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter


class Fundable(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.get("https://www.tryfundable.ai/api/v1/company",
                        headers={"Authorization": f"Bearer {self.key('FUNDABLE_API_KEY')}", "Accept": "application/json"},
                        params={"domain": company.domain})

    def not_found(self, body: dict[str, Any]) -> str | None:
        if (body.get("data") or {}).get("company"):
            return None
        error = body.get("error")
        if isinstance(error, dict):
            return error.get("message") or "no company"
        return error if isinstance(error, str) and error else "no company"

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        company = (body.get("data") or {}).get("company") or {}
        deal = company.get("latest_deal") or {}
        stage = deal.get("type")
        if stage and deal.get("pre"):
            stage = f"pre {stage}"
        return {"latest_stage": stage, "latest_date": deal.get("date"), "latest_amount": deal.get("total_round_raised"),
                "total_raised": company.get("total_raised"), "round_count": company.get("num_funding_rounds")}


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Fundable:
    return Fundable(setup, spec, env)
