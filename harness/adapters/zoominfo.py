"""ZoomInfo company funding through the `gtm` CLI, several domains per call. The CLI uses its own sign-in."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from ..models import Answer, Company
from ..question import funding_fields
from ..tool_base import Adapter


def usd_thousands(value: object) -> int | float | None:
    """ZoomInfo funding amounts are in thousands of USD; the benchmark uses USD."""
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = Decimal(str(value)) * 1000
    except (InvalidOperation, ValueError):
        return None
    return int(converted) if converted == converted.to_integral_value() else float(converted)


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    rows = sorted((r for r in data.get("companyFunding") or [] if isinstance(r, dict)),
                  key=lambda r: str(r.get("date") or ""), reverse=True)
    latest = rows[0] if rows else {}
    amount = usd_thousands(latest.get("amount"))
    total = usd_thousands(data.get("totalFundingAmount"))
    return {
        "latest_stage": latest.get("type"),
        "latest_announced_on": (latest.get("date") or "").split("T", 1)[0] or None,
        "latest_amount": amount,
        "currency": "USD" if amount is not None or total is not None else None,
        "total_raised": total,
        "funding_round_count": len(rows) or None,
    }


class ZoomInfo(Adapter):
    def __init__(self, setup: str, spec: dict[str, Any], env: list[str]) -> None:
        super().__init__(setup, spec, env)
        self.batch_size = int(self.settings.get("domains_per_call") or 1)

    def missing_env(self) -> list[str]:
        return [] if shutil.which("gtm") else ["gtm CLI"]

    def lookup(self, company: Company) -> Answer:
        return self.lookup_many([company])[0]

    def lookup_many(self, companies: list[Company]) -> list[Answer]:
        started = time.perf_counter()
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump([{"domain": c.domain} for c in companies], handle)
            handle.flush()
            result = subprocess.run(
                ["gtm", "companies", "enrich", "--file", handle.name, "--fields", *self.settings["fields"], "--format", "json"],
                check=False, capture_output=True, text=True, timeout=180,
            )
        latency = round((time.perf_counter() - started) * 1000)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[:300] or f"gtm exited {result.returncode}")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError("gtm returned a non-object response")
        answers = []
        # The CLI answers in input order under company_1, company_2, ...
        for index, company in enumerate(companies, start=1):
            item = payload.get(f"company_{index}")
            item = item if isinstance(item, dict) else {}
            data = item.get("data") or {}
            found = bool(item.get("success")) and bool(data)
            answers.append(self.answer(company, "ok" if found else "not_found", funding_fields(normalize(data)) if found else {},
                                       error=None if found else "ZoomInfo returned no company match",
                                       latency_ms=latency, cost_units=1 if found else None,
                                       cost_unit="credit" if found else None, raw=item))
        return answers


def build(setup: str, spec: dict[str, Any], env: list[str]) -> ZoomInfo:
    return ZoomInfo(setup, spec, env)
