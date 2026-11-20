"""CompanyEnrich company enrichment by domain."""
from __future__ import annotations

from typing import Any

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter, latest_round


class CompanyEnrich(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.get("https://api.companyenrich.com/companies/enrich",
                        headers={"Authorization": f"Bearer {self.key('COMPANY_ENRICH_API_KEY')}", "Accept": "application/json"},
                        params={"domain": company.domain})

    def not_found(self, body: dict[str, Any]) -> str | None:
        return None if body.get("id") else "no company"

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        item = body.get("financial") or {}
        result = latest_round(item.get("funding") or [], date_key="date", stage_key="type", amount_key="amount")
        result["latest_stage"] = result["latest_stage"] or item.get("funding_stage")
        result["latest_date"] = result["latest_date"] or item.get("funding_date")
        result["total_raised"] = item.get("total_funding")
        return result


def build(setup: str, spec: dict[str, Any], env: list[str]) -> CompanyEnrich:
    return CompanyEnrich(setup, spec, env)
