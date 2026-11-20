"""People Data Labs company enrichment by website."""
from __future__ import annotations

from typing import Any

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter


class PeopleDataLabs(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.get("https://api.peopledatalabs.com/v5/company/enrich",
                        headers={"X-Api-Key": self.key("PEOPLE_DATA_LABS_API_KEY"), "Accept": "application/json"},
                        params={"website": company.domain})

    def not_found(self, body: dict[str, Any]) -> str | None:
        return None if body.get("id") else "no company"

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        return {"latest_stage": body.get("latest_funding_stage"), "latest_date": body.get("last_funding_date"),
                "latest_amount": None, "total_raised": body.get("total_funding_raised"),
                "round_count": body.get("number_funding_rounds")}

    def cost(self, response: Response) -> tuple[float | None, str | None]:
        try:
            return float(response.headers["x-call-credits-spent"]), "credit"
        except (KeyError, ValueError):
            return None, None


def build(setup: str, spec: dict[str, Any], env: list[str]) -> PeopleDataLabs:
    return PeopleDataLabs(setup, spec, env)
