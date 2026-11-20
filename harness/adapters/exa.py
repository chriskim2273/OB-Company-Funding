"""Exa: /search with an output schema (exa, exa-instant), or the Agent API at a fixed effort (exa-agent)."""
from __future__ import annotations

import time
from typing import Any

from ..models import Answer, Company
from ..question import OUTPUT_SCHEMA, funding_fields, instruction
from ._research import ResearchAdapter

POLL_SECONDS = 5
POLL_ATTEMPTS = 120


class Exa(ResearchAdapter):
    def lookup(self, company: Company) -> Answer:
        return self._agent(company) if "effort" in self.settings else self._search(company)

    def _search(self, company: Company) -> Answer:
        payload = {"query": instruction(company), "type": self.settings["type"], "output_schema": OUTPUT_SCHEMA}
        response = self.call("POST", "https://api.exa.ai/search",
                             {"x-api-key": self.key("EXA_API_KEY"), "Content-Type": "application/json"}, payload)
        body = response.body if isinstance(response.body, dict) else {}
        output = body.get("output")
        if not isinstance(output, dict) or "content" not in output:
            raise ValueError(f"Exa {self.settings['type']} returned no structured output (keys: {sorted(body)[:8]})")
        cost = (body.get("costDollars") or {}).get("total")
        return self.answer(company, "ok", funding_fields(output["content"]), latency_ms=response.latency_ms,
                           cost_units=cost, cost_unit="usd" if cost is not None else None, raw=body)

    def _agent(self, company: Company) -> Answer:
        # The Agent API takes a bearer token and spells the schema `outputSchema`; /search uses x-api-key and `output_schema`.
        headers = {"Authorization": f"Bearer {self.key('EXA_API_KEY')}", "Content-Type": "application/json"}
        payload = {"query": instruction(company), "effort": self.settings["effort"], "outputSchema": OUTPUT_SCHEMA}
        started = time.perf_counter()
        body = self.call("POST", "https://api.exa.ai/agent/runs", headers, payload, timeout=600).body or {}
        run_id = body.get("id")
        for _ in range(POLL_ATTEMPTS):
            status = body.get("status")
            if status in {"failed", "cancelled"}:
                raise ValueError(f"Exa agent run {status}: {body.get('error') or body.get('message')}")
            if status == "completed":
                break
            if not run_id:
                raise ValueError(f"Exa agent returned no run id (status {status!r})")
            time.sleep(POLL_SECONDS)
            body = self.call("GET", f"https://api.exa.ai/agent/runs/{run_id}", headers, timeout=600).body or {}
        output = body.get("output") or {}
        structured = output.get("structured") if isinstance(output, dict) else None
        if not isinstance(structured, dict):
            if body.get("status") != "completed":
                raise TimeoutError("Exa agent run did not complete in time")
            text = output.get("text") if isinstance(output, dict) else None
            if not isinstance(text, str):
                raise ValueError("Exa agent returned neither structured output nor text")
            structured = {"unparsed_text": text}  # Prose instead of the schema is the result; it scores nothing.
        cost = (body.get("costDollars") or {}).get("total")
        return self.answer(company, "ok", funding_fields(structured), latency_ms=round((time.perf_counter() - started) * 1000),
                           cost_units=cost, cost_unit="usd" if cost is not None else None,
                           raw={"response": body, "run_id": run_id, "usage": body.get("usage")})


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Exa:
    return Exa(setup, spec, env)
