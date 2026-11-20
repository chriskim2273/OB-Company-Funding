"""Seltz: the Answer API at a scope, the companies Search API read as structured records, or Search plus extraction."""
from __future__ import annotations

import json
import re
from typing import Any

from ..models import Answer, Company
from ..question import OUTPUT_SCHEMA, funding_fields, instruction, parse_json_answer
from ._extraction import extract
from ._research import HttpError, ResearchAdapter

ANSWER_URL = "https://api.seltz.ai/v1/answer"
SEARCH_URL = "https://api.seltz.ai/v1/search"
SYSTEM_PROMPT = (
    "You are a funding data extraction service. Answer only with a single JSON object "
    "matching this schema, and nothing else: "
    + json.dumps(OUTPUT_SCHEMA)
    + " Amounts are whole major-currency units, never millions or billions. "
    "Use null for any field you cannot verify. Do not infer."
)
TOTAL_RAISED = re.compile(r"Total funding raised:\s*\$?\s*([\d,]+(?:\.\d+)?)", re.I)
EMPTY = {field: None for field in OUTPUT_SCHEMA["properties"]}


class Seltz(ResearchAdapter):
    def lookup(self, company: Company) -> Answer:
        if "extractor" in self.settings:
            return self._search_and_extract(company)
        if "fields" in self.settings:
            return self._structured(company)
        return self._answer(company)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.key("SELTZ_API_KEY"), "Content-Type": "application/json"}

    def _answer_payload(self, company: Company, json_schema: bool) -> dict[str, Any]:
        return {"query": instruction(company), "scope": self.settings["scope"], "system_prompt": SYSTEM_PROMPT,
                "response_format": ({"type": "json_schema", "json_schema": {"name": "funding_event", "schema": OUTPUT_SCHEMA}}
                                    if json_schema else {"type": "json_object"})}

    def _answer(self, company: Company) -> Answer:
        # The docs show only json_object. json_schema is tried first because it is stricter; the mode used is recorded.
        mode = "json_schema"
        try:
            response = self.call("POST", ANSWER_URL, self._headers(), self._answer_payload(company, True))
        except HttpError as error:
            if error.response.status not in {400, 404, 415, 422}:
                raise
            mode = "json_object"
            response = self.call("POST", ANSWER_URL, self._headers(), self._answer_payload(company, False))
        body = response.body if isinstance(response.body, dict) else {}
        answer = body.get("answer")
        if not isinstance(answer, str):
            raise ValueError("Seltz returned no answer text")
        citations = [c.get("url") for c in body.get("citations") or [] if isinstance(c, dict) and c.get("url")]
        return self.answer(company, "ok", funding_fields(parse_json_answer(answer)), latency_ms=response.latency_ms,
                           cost_units=1, cost_unit="request",
                           raw={"response": body, "response_format_mode": mode, "sources": list(dict.fromkeys(citations))})

    def _structured(self, company: Company) -> Answer:
        payload = {"query": f"{company.name or ''} {company.domain}".strip(), "scope": self.settings["scope"],
                   "max_results": self.settings["max_results"], "fields": self.settings["fields"]}
        response = self.call("POST", SEARCH_URL, self._headers(), payload)
        body = response.body if isinstance(response.body, dict) else {}
        documents = [d for d in body.get("documents") or [] if isinstance(d, dict)]
        # Seltz's first result with a company record is its answer; whether it is the right company is for the judge.
        document = next((d for d in documents if (d.get("properties") or {}).get("company")), None)
        normalized = record_fields(document) if document else dict(EMPTY)
        return self.answer(company, "ok", funding_fields(normalized), latency_ms=response.latency_ms,
                           cost_units=1, cost_unit="request",
                           raw={"response": body, "answer_url": document.get("url") if document else None})

    def _search_and_extract(self, company: Company) -> Answer:
        payload = {"query": instruction(company), "scope": self.settings["scope"], "max_results": self.settings["max_results"]}
        response = self.call("POST", SEARCH_URL, self._headers(), payload)
        body = response.body if isinstance(response.body, dict) else {}
        hits = [{"url": d["url"], "published_date": d.get("published_date"),
                 "snippet": d.get("content") or "\n".join(
                     (s.get("text") if isinstance(s, dict) else str(s)) for s in d.get("snippets") or [])}
                for d in body.get("documents") or [] if isinstance(d, dict) and d.get("url")][: self.settings["max_results"]]
        raw: dict[str, Any] = {"response": body, "search_evidence": hits}
        if not hits:
            return self.answer(company, "ok", funding_fields(dict(EMPTY)), latency_ms=response.latency_ms,
                               cost_units=1, cost_unit="request", raw=raw)
        value, audit = extract(company, hits, self.settings["extractor"])
        raw["extraction"] = audit
        return self.answer(company, "ok", funding_fields(value), latency_ms=response.latency_ms + audit["latency_ms"],
                           cost_units=1, cost_unit="request", raw=raw)


def record_fields(document: dict[str, Any]) -> dict[str, Any]:
    """The funding fields from one Seltz company record. Total raised comes from the profile text when Seltz states it."""
    company = (document.get("properties") or {}).get("company") or {}
    rounds = [r for r in company.get("funding_rounds") or [] if isinstance(r, dict)]
    dated = sorted((r for r in rounds if r.get("date")), key=lambda r: str(r["date"])[:10])
    latest = dated[-1] if dated else (rounds[-1] if rounds else {})
    amount = latest.get("amount")
    total = TOTAL_RAISED.search(str(document.get("content") or ""))
    return {
        "latest_stage": latest.get("type") or None,
        "latest_announced_on": str(latest["date"])[:10] if latest.get("date") else None,
        "latest_amount": int(amount) if isinstance(amount, (int, float)) and amount > 0 else None,
        "currency": latest.get("currency") or None,
        "total_raised": int(float(total.group(1).replace(",", ""))) if total else None,
        "funding_round_count": len(rounds) or None,
    }


def build(setup: str, spec: dict[str, Any], env: list[str]) -> Seltz:
    return Seltz(setup, spec, env)
