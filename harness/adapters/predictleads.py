"""PredictLeads financing events for a domain."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..http_client import Response
from ..models import Company
from ._common import DataApiAdapter


class PredictLeads(DataApiAdapter):
    def call(self, company: Company) -> Response:
        return self.get(f"https://predictleads.com/api/v3/companies/{quote(company.domain)}/financing_events",
                        headers={"X-Api-Key": self.key("PREDICTLEADS_API_KEY"),
                                 "X-Api-Token": self.key("PREDICTLEADS_API_TOKEN"), "Accept": "application/json"})

    def not_found(self, body: dict[str, Any]) -> str | None:
        return None if body.get("data") else "no financing events"

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        records = [row.get("attributes") or {} for row in body.get("data") or [] if isinstance(row, dict)]
        records.sort(key=lambda row: str(row.get("effective_date") or row.get("found_at") or ""), reverse=True)
        record = records[0] if records else {}
        return {"latest_stage": record.get("financing_type_normalized") or record.get("financing_type"),
                "latest_date": record.get("effective_date"), "latest_date_observed_at": record.get("found_at"),
                "latest_amount": record.get("amount_normalized") or record.get("amount"), "total_raised": None,
                "round_count": len(records)}


def build(setup: str, spec: dict[str, Any], env: list[str]) -> PredictLeads:
    return PredictLeads(setup, spec, env)
