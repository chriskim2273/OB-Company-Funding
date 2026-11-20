"""Crustdata company enrichment for several domains per request, asking only for the funding fields."""
from __future__ import annotations

from typing import Any

from .. import http_client
from ..models import Answer, Company
from ..question import funding_fields
from ._common import envelope, http_failure
from ..tool_base import Adapter

URL = "https://api.crustdata.com/company/enrich"


def choose(matches: list[dict[str, Any]], domain: str) -> dict[str, Any] | None:
    """Highest confidence wins; an exact primary-domain match breaks a tie."""
    if not matches:
        return None
    return max(matches, key=lambda m: (
        m.get("confidence_score") or 0,
        (((m.get("company_data") or {}).get("basic_info") or {}).get("primary_domain") or "").lower() == domain.lower(),
    ))


class Crustdata(Adapter):
    def __init__(self, setup: str, spec: dict[str, Any], env: list[str]) -> None:
        super().__init__(setup, spec, env)
        self.batch_size = int(self.settings.get("domains_per_request") or 1)

    def lookup(self, company: Company) -> Answer:
        return self.lookup_many([company])[0]

    def lookup_many(self, companies: list[Company]) -> list[Answer]:
        headers = {"authorization": f"Bearer {self.key('CRUSTDATA_API_KEY')}", "content-type": "application/json",
                   "x-api-version": "2025-11-01"}
        payload = {"domains": [c.domain for c in companies], "exact_match": self.settings["exact_match"],
                   "fields": list(self.settings["fields"])}
        response = http_client.request("POST", URL, headers=headers, json=payload, timeout=120)
        failure = http_failure(response)
        if failure:
            raw = envelope(response)
            return [self.answer(c, failure[0], error=failure[1], latency_ms=response.latency_ms, raw=raw) for c in companies]
        items = response.body if isinstance(response.body, list) else []
        by_input = {str(item.get("matched_on", "")).lower(): item for item in items if isinstance(item, dict)}
        answers = []
        for company in companies:
            entry = by_input.get(company.domain.lower(), {})
            selected = choose(entry.get("matches") or [], company.domain)
            data = (selected or {}).get("company_data") or {}
            funding = data.get("funding") or {}
            normalized = {
                "latest_stage": funding.get("last_round_type"),
                "latest_announced_on": funding.get("last_fundraise_date"),
                "latest_amount": funding.get("last_round_amount_usd"),
                "currency": "USD" if funding.get("last_round_amount_usd") is not None else None,
                "total_raised": funding.get("total_investment_usd"),
            }
            answers.append(self.answer(company, "ok" if data else "not_found", funding_fields(normalized) if data else {},
                                       error=None if data else "no match", latency_ms=response.latency_ms,
                                       cost_units=1, cost_unit="credit",
                                       raw={"envelope": entry, "selected_match": selected}))
        return answers


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Crustdata:
    return Crustdata(setup, spec, env)
