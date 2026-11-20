"""Explorium: match the domain to a business id, then ask for its funding and acquisition data."""
from __future__ import annotations

from typing import Any

from ..models import Answer, Company
from ..question import funding_fields
from ._common import DataApiAdapter, envelope, http_failure


class Explorium(DataApiAdapter):
    def lookup(self, company: Company) -> Answer:
        headers = {"api_key": self.key("EXPLORIUM_API_KEY"), "Content-Type": "application/json"}
        matched = self.post("https://api.explorium.ai/v1/businesses/match", headers=headers,
                            json={"businesses_to_match": [{"domain": company.domain}]})
        raw: dict[str, Any] = {"match": envelope(matched)}
        failure = http_failure(matched)
        if failure:
            return self.answer(company, failure[0], error=failure[1], latency_ms=matched.latency_ms, raw=raw)
        body = matched.body if isinstance(matched.body, dict) else {}
        business_id = next((item.get("business_id") or item.get("businessId")
                            for item in body.get("matched_businesses") or [] if isinstance(item, dict)), None)
        if not business_id:
            return self.answer(company, "not_found", error="match returned no business_id",
                               latency_ms=matched.latency_ms, cost_units=1, cost_unit="request", raw=raw)
        enriched = self.post("https://api.explorium.ai/v1/businesses/funding_and_acquisition/bulk_enrich",
                             headers=headers, json={"business_ids": [business_id]})
        raw["funding_enrichment"] = envelope(enriched)
        latency = matched.latency_ms + enriched.latency_ms
        failure = http_failure(enriched)
        if failure:
            return self.answer(company, failure[0], error=failure[1], latency_ms=latency, raw=raw)
        data = (enriched.body or {}).get("data") if isinstance(enriched.body, dict) else None
        if not data:
            return self.answer(company, "not_found", error="no funding enrichment", latency_ms=latency,
                               cost_units=2, cost_unit="request", raw=raw)
        item = (data[0] or {}).get("data") or {}
        normalized = {"latest_stage": item.get("last_funding_round_type"), "latest_date": item.get("last_funding_round_date"),
                      "latest_amount": item.get("last_funding_round_value_usd"),
                      "total_raised": item.get("known_funding_total_value"), "round_count": item.get("number_of_funding_rounds")}
        return self.answer(company, "ok", funding_fields(normalized), latency_ms=latency,
                           cost_units=2, cost_unit="request", raw=raw)


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Explorium:
    return Explorium(setup, spec, env)
