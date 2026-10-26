"""Load the benchmark table and curated charities, and enforce the sourcing rules.

Rule: a number is only used if it has a source link, a date, and a verbatim quote that
contains it. Anything else is downgraded to "missing" with the reason shown to the user.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from app import calculator, config

RESEARCH_DIR = config.DATA_DIR / "research"

_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(million|billion|thousand)?", re.I)
_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9}


def numbers_in(text: str) -> list[float]:
    out = []
    for digits, scale in _NUM.findall(text or ""):
        try:
            v = float(digits.replace(",", ""))
        except ValueError:
            continue
        out.append(v)
        if scale:
            out.append(v * _SCALE[scale.lower()])
    return out


def _in_quote(value: float, quote: str) -> bool:
    if value == 100 and re.search(r"\d\s*(%|percent)", quote, re.I):   # "140%" is 140 per 100
        return True
    return any(abs(n - value) <= 1e-9 * max(1.0, abs(value)) for n in numbers_in(quote))


def provenance_problems(item: dict, values: list[float | None]) -> list[str]:
    problems = []
    url = item.get("source_url") or ""
    if not url.startswith(("http://", "https://")):
        problems.append("no source link")
    if not (item.get("source_date") or item.get("accessed")):
        problems.append("no date")
    quote = item.get("quote") or ""
    if not quote.strip():
        problems.append("no quote")
    for v in values:
        if v is None:
            problems.append("value is empty")
        elif v != 1 and quote and not _in_quote(v, quote):   # 1 is implied by "per DALY" etc.
            problems.append(f"{v:g} does not appear in the quote")
    return problems


def _check(item: dict, values: list[float | None]) -> dict:
    item = dict(item)
    item["warnings"] = []
    if item.get("status") != "sourced":
        item["status"] = "missing"
        item.setdefault("missing_reason", item.get("notes") or "No source found for this number.")
        return item
    problems = provenance_problems(item, values)
    if problems:
        item["status"] = "missing"
        item["missing_reason"] = "Not used: " + "; ".join(problems) + "."
    elif not item.get("source_date"):
        item["warnings"].append("Source page shows no publication date; accessed date given.")
    return item


def _benchmark(b: dict) -> dict:
    """A benchmark is either a stated value, or stated inputs the calculator turns into a value."""
    inp = b.get("inputs")
    if not inp:
        return _check(b, [b.get("value")])
    b = _check(b, [inp.get("cost_usd"), inp.get("outcome_amount")])
    if b["status"] == "sourced":
        res = calculator.compute_metric(b["cause"], inp.get("cost_usd"), inp.get("outcome_amount"),
                                        inp.get("outcome_unit"))
        b["value"] = res.value
        if not res.ok:
            b["status"], b["missing_reason"] = "missing", res.reason
    return b


@lru_cache(maxsize=1)
def load() -> dict:
    benchmarks, charities = [], []
    for f in sorted(RESEARCH_DIR.glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        for b in raw.get("benchmarks", []):
            if b.get("cause") in calculator.CAUSES:
                benchmarks.append(_benchmark(b))
        for c in raw.get("charities", []):
            if c.get("cause") in calculator.CAUSES:
                inp = c.get("inputs") or {}
                charities.append(_check(c, [inp.get("cost_usd"), inp.get("outcome_amount")]))
    return {"benchmarks": benchmarks, "charities": charities}


def primary_benchmark(cause: str) -> dict | None:
    for b in load()["benchmarks"]:
        if b["cause"] == cause and b.get("role") == "primary":
            return b
    return None


def benchmark_value(cause: str) -> float | None:
    b = primary_benchmark(cause)
    return b.get("value") if b and b.get("status") == "sourced" else None


def cause_view(cause: str) -> dict:
    """Everything the donor view needs for one cause, computed in plain code."""
    spec = calculator.CAUSES[cause]
    data = load()
    bench_val = benchmark_value(cause)
    ranking = calculator.rank_charities(cause, data["charities"], bench_val)
    for group in ranking.values():
        for row in group:
            row["display"] = calculator.format_metric(cause, row["result"]["value"])
    return {
        "cause": cause, "label": spec.label, "metric_label": spec.metric_label,
        "lower_is_better": spec.lower_is_better,
        "benchmark": primary_benchmark(cause),
        "benchmark_display": calculator.format_metric(cause, bench_val),
        "references": [b for b in data["benchmarks"] if b["cause"] == cause and b.get("role") != "primary"],
        **ranking,
    }
