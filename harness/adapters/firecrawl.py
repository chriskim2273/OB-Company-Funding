"""Firecrawl Agent with the setup's model and a per-run credit cap."""
from __future__ import annotations

import time
from typing import Any

from ..models import Answer, Company
from ..question import OUTPUT_SCHEMA, funding_fields, instruction
from ._research import ResearchAdapter

POLL_SECONDS = 5
POLL_ATTEMPTS = 120


class Firecrawl(ResearchAdapter):
    def lookup(self, company: Company) -> Answer:
        headers = {"Authorization": f"Bearer {self.key('FIRECRAWL_API_KEY')}", "Content-Type": "application/json"}
        payload = {"prompt": instruction(company), "model": self.settings["model"], "schema": OUTPUT_SCHEMA,
                   "maxCredits": self.settings["max_credits"]}
        started = time.perf_counter()
        body = self.call("POST", "https://api.firecrawl.dev/v2/agent", headers, payload).body or {}
        job_id = body.get("id") or body.get("jobId")
        for _ in range(POLL_ATTEMPTS):
            status = body.get("status")
            if status in {"failed", "cancelled"}:
                raise ValueError(f"Firecrawl agent {status}: {body.get('error') or body.get('message')}")
            if status == "completed" or body.get("data") is not None:
                break
            if not job_id:
                raise ValueError(f"Firecrawl returned no data and no job id (status {status!r})")
            time.sleep(POLL_SECONDS)
            # A job is not always queryable the moment its id comes back, so a 404 here means "ask again".
            polled = self.call("GET", f"https://api.firecrawl.dev/v2/agent/{job_id}", headers, ok_statuses=frozenset({404}))
            if polled.ok:
                body = polled.body or {}
        data = body.get("data")
        if data is None:
            raise TimeoutError(f"Firecrawl agent did not return data within {self.settings.get('timeout_seconds')}s")
        # Some responses nest the object under the schema name; unwrap only when the flat shape is clearly absent.
        if isinstance(data, dict) and "latest_stage" not in data and len(data) == 1:
            inner = next(iter(data.values()))
            if isinstance(inner, dict):
                data = inner
        credits = body.get("creditsUsed")
        return self.answer(company, "ok", funding_fields(data if isinstance(data, dict) else {}),
                           latency_ms=round((time.perf_counter() - started) * 1000),
                           cost_units=credits, cost_unit="credit" if credits is not None else None, raw={"response": body})


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Firecrawl:
    return Firecrawl(setup, spec, env)
