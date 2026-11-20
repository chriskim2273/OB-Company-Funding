"""Helpers shared by the adapters. Adapters call `http_client.request` through the module so tests can replace it."""
from __future__ import annotations

from typing import Any

from .. import http_client
from ..http_client import Response
from ..models import Answer, Company
from ..question import funding_fields
from ..tool_base import Adapter


def envelope(response: Response) -> dict[str, Any]:
    """What is saved of one HTTP response."""
    return {"http_status": response.status, "latency_ms": response.latency_ms, "headers": response.headers, "response": response.body}


def http_failure(response: Response) -> tuple[str, str] | None:
    """None for a 2xx response; otherwise the answer status and error. HTTP 404 means the tool has no such company."""
    if response.ok:
        return None
    if response.status == 404:
        return "not_found", "HTTP 404"
    body = response.body if isinstance(response.body, dict) else {}
    message = body.get("message") or body.get("error") or body.get("detail") or ""
    return "error", f"HTTP {response.status}: {message}"[:300].rstrip(": ")


def first_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value") if "value" in value else value
    return value


def latest_round(rounds: Any, *, date_key: str, stage_key: str, amount_key: str) -> dict[str, Any]:
    rows = [row for row in rounds or [] if isinstance(row, dict)]
    rows.sort(key=lambda row: str(row.get(date_key) or ""), reverse=True)
    row = rows[0] if rows else {}
    return {"latest_stage": row.get(stage_key), "latest_date": row.get(date_key), "latest_amount": row.get(amount_key),
            "round_count": len(rows)}


class DataApiAdapter(Adapter):
    """A company-data API asked once per company by domain: request, a no-match check, and a parser."""

    timeout = 45.0

    def call(self, company: Company) -> Response:
        raise NotImplementedError

    def not_found(self, body: dict[str, Any]) -> str | None:
        """The reason the response holds no company, or None when it does."""
        raise NotImplementedError

    def parse(self, body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def cost(self, response: Response) -> tuple[float | None, str | None]:
        return None, None

    def lookup(self, company: Company) -> Answer:
        response = self.call(company)
        raw = envelope(response)
        failure = http_failure(response)
        if failure:
            status, error = failure
            return self.answer(company, status, error=error, latency_ms=response.latency_ms, raw=raw)
        body = response.body if isinstance(response.body, dict) else {}
        units, unit = self.cost(response)
        reason = self.not_found(body)
        if reason:
            return self.answer(company, "not_found", error=reason, latency_ms=response.latency_ms,
                               cost_units=units, cost_unit=unit, raw=raw)
        return self.answer(company, "ok", funding_fields(self.parse(body)), latency_ms=response.latency_ms,
                           cost_units=units, cost_unit=unit, raw=raw)

    def get(self, url: str, **kwargs: Any) -> Response:
        return http_client.request("GET", url, timeout=self.timeout, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return http_client.request("POST", url, timeout=self.timeout, **kwargs)
