"""Deterministic grader for Company Funding: latest_stage, amount (+-5%), announced_on (+-7 days)."""
from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((HERE / "config.yaml").read_text())
ALIASES = json.loads((HERE / "stage_aliases.json").read_text())

SERIES_RE = re.compile(r"^(?:series\s+)?([a-z])(?:\s*(?:\d+|\+|plus|extension))?$")


def _norm_label(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    if " - " in s:
        s = s.split(" - ", 1)[0]
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    stripped = re.sub(r"\b(?:round|financing)\b", "", s)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or s


STAGE_FIELD = CONFIG["judge"]["fields"]["latest_stage"]
ADDITIONS = STAGE_FIELD.get("additions") or {}
RULES = STAGE_FIELD.get("rules") or {}

# stage_aliases.json `special.early_stage`: "Early Stage key accepts Seed or Pre-Seed only."
EARLY_STAGE_ACCEPTS = frozenset({"seed_group", "pre_seed"})
# Reference labels that carry no stage at all. They are scored like a blank reference.
BLANK_LABELS = frozenset({"none", "n/a"})


def _build_stage_map() -> dict[str, str]:
    """Label -> canonical stage. Later sources win: table aliases, table groups, then config additions."""
    mapping: dict[str, str] = {}
    for alias, name in (ALIASES.get("aliases") or {}).items():
        mapping[_norm_label(alias)] = name
    for group_name, info in (ALIASES.get("groups") or {}).items():
        for member in info.get("members", []):
            mapping[_norm_label(member)] = group_name
    for alias, name in (ADDITIONS.get("aliases") or {}).items():
        mapping[_norm_label(alias)] = name
    return mapping


STAGE_MAP = _build_stage_map()


def canonical_stage(raw: str | None) -> str:
    norm = _norm_label(raw)
    if not norm:
        return ""
    m = SERIES_RE.match(norm)
    if m and norm not in STAGE_MAP:
        return f"series_{m.group(1)}"
    return STAGE_MAP.get(norm, norm)


def grade_stage(truth: str | None, pred: str | None) -> str:
    t_can = canonical_stage(truth)
    if not t_can or t_can in BLANK_LABELS:
        return RULES.get("blank_key", "not_scoreable")
    if t_can == "undisclosed":
        return RULES.get("undisclosed_key", "not_scoreable")
    if t_can == "nostage":
        return RULES.get("key_no_stage", "not_scoreable")
    p_can = canonical_stage(pred)
    if t_can == "early_stage":
        return "correct" if p_can in EARLY_STAGE_ACCEPTS else "wrong"
    if not p_can or p_can == "nostage":
        return "wrong"
    if t_can == p_can:
        return "correct"
    for pair in ADDITIONS.get("same_class") or []:
        if {t_can, p_can} == set(pair):
            return "correct"
    accepted = (ADDITIONS.get("key_accepts") or {}).get(t_can) or []
    if p_can in accepted:
        return "correct"
    return "wrong"


def grade_amount(truth: float | int | None, pred: float | int | None, pct: float = 5.0) -> str:
    if truth is None or truth <= 0:
        return "not_scoreable"
    if pred is None or pred <= 0:
        return "wrong"
    return "correct" if abs(float(pred) - float(truth)) / float(truth) <= (pct / 100.0) else "wrong"


def grade_date(truth: str | None, pred: str | None, days: int = 7) -> str:
    if not truth:
        return "not_scoreable"
    if not pred:
        return "wrong"
    try:
        d_truth = date.fromisoformat(str(truth)[:10])
        d_pred = date.fromisoformat(str(pred)[:10])
    except ValueError:
        return "wrong"
    return "correct" if abs((d_pred - d_truth).days) <= days else "wrong"


def grade_row(truth: dict[str, Any], pred: dict[str, Any]) -> dict[str, str]:
    fields = CONFIG["judge"]["fields"]
    return {
        "latest_stage": grade_stage(truth.get("latest_stage"), pred.get("latest_stage")),
        "amount": grade_amount(truth.get("amount"), pred.get("amount"), pct=fields["amount"]["percent"]),
        "announced_on": grade_date(truth.get("announced_on"), pred.get("announced_on"), days=fields["announced_on"]["days"]),
    }


def wilson95(correct: int, total: int) -> tuple[float, float, float]:
    if total <= 0:
        return (0.0, 0.0, 0.0)
    z = 1.959963984540054
    p = correct / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = (z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))
