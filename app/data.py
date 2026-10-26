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


PRESENTATION = config.DATA_DIR / "presentation.json"
RANGES = RESEARCH_DIR / "ranges.json"


@lru_cache(maxsize=1)
def presentation() -> dict:
    return json.loads(PRESENTATION.read_text(encoding="utf-8"))


def _present(item: dict) -> dict:
    """Merge wording, measure and kind from presentation.json into one researched item."""
    pres = presentation()
    items = pres.get("items", {})
    extra = dict(items.get(f"{item['cause']}:{item['id']}", {}))
    plain = items.get(item["id"], {})
    if plain.get("_cause") in (None, item["cause"]):
        extra = {**plain, **extra}
    extra.pop("_cause", None)
    out = {**item, **extra}
    out.setdefault("kind", "charity")
    out.setdefault("measure", pres["default_measure"][item["cause"]])
    out["measure_label"] = pres["measures"].get(out["measure"], out["measure"])
    if out.get("display_name"):
        out["research_name"], out["name"] = out.get("name"), out["display_name"]
    return out


def _range(item: dict, ranges: dict) -> dict | None:
    """A published range, only if the source states it and both bounds are in its quote."""
    r = ranges.get(item["id"])
    if not r or r.get("status") != "stated" or not r.get("quote"):
        return None
    if r.get("source_url") and item.get("source_url") and r["source_url"] != item["source_url"]:
        return None
    vals = []
    for side in ("low", "high"):
        inp = r.get(side) or {}
        if provenance_problems({"source_url": item.get("source_url"), "accessed": r.get("accessed"),
                                "quote": r["quote"]}, [inp.get("cost_usd"), inp.get("outcome_amount")]):
            return None
        res = calculator.compute_metric(item["cause"], inp.get("cost_usd"), inp.get("outcome_amount"))
        if not res.ok:
            return None
        vals.append(res.value)
    lo, hi = sorted(vals)
    return {"low": lo, "high": hi, "kind": r.get("kind"), "quote": r["quote"], "note": r.get("note"),
            "display": (f"${lo:,.2f} to ${hi:,.2f} per $1" if item["cause"] == "poverty" else
                        f"{calculator.format_metric(item['cause'], lo)} to {calculator.format_metric(item['cause'], hi)}")}


@lru_cache(maxsize=1)
def load() -> dict:
    benchmarks, charities = [], []
    try:
        raw_ranges = json.loads(RANGES.read_text(encoding="utf-8")).get("ranges", [])
    except FileNotFoundError:
        raw_ranges = []
    ranges = {r["id"]: r for r in raw_ranges if r.get("id")}
    for f in sorted(RESEARCH_DIR.glob("*.json")):
        if f == RANGES:
            continue
        raw = json.loads(f.read_text(encoding="utf-8"))
        for b in raw.get("benchmarks", []):
            if b.get("cause") in calculator.CAUSES:
                b = _present(_benchmark(b))
                b["range"] = _range(b, ranges) if b["status"] == "sourced" else None
                benchmarks.append(b)
        for c in raw.get("charities", []):
            if c.get("cause") in calculator.CAUSES:
                inp = c.get("inputs") or {}
                c = _present(_check(c, [inp.get("cost_usd"), inp.get("outcome_amount")]))
                c["range"] = _range(c, ranges) if c["status"] == "sourced" else None
                charities.append(c)
    return {"benchmarks": benchmarks, "charities": charities}


def primary_benchmark(cause: str) -> dict | None:
    for b in load()["benchmarks"]:
        if b["cause"] == cause and b.get("role") == "primary":
            return b
    return None


def benchmark_value(cause: str) -> float | None:
    b = primary_benchmark(cause)
    return b.get("value") if b and b.get("status") == "sourced" else None


def benchmark_measure(cause: str) -> str:
    b = primary_benchmark(cause)
    return b["measure"] if b else presentation()["default_measure"][cause]


def comparable(item: dict) -> bool:
    """Only items in the benchmark's own measure are compared with it."""
    return item.get("measure", benchmark_measure(item["cause"])) == benchmark_measure(item["cause"])


DIFFERENT_MEASURE = {"ok": False, "times_benchmark": None, "band": None, "label": None,
                     "reason": "Uses a different measure from the benchmark, so it is not compared."}


def _decorate(cause: str, row: dict) -> dict:
    row["display"] = calculator.format_metric(cause, row["result"]["value"])
    row["range_display"] = row["range"]["display"] if row.get("range") else None
    if not row["result"]["ok"]:
        row["donor_note"] = row.get("donor_note") or "No published estimate in this cause's measure was found."
        row["details"] = row["result"].get("reason")
    return row


def cause_view(cause: str) -> dict:
    """Everything the donor view needs for one cause, computed in plain code.

    Charities are ranked only against others in the same measure. General program types are
    listed separately and never ranked with charities.
    """
    spec = calculator.CAUSES[cause]
    pres = presentation()
    items = [c for c in load()["charities"] if c["cause"] == cause]
    charities = [c for c in items if c["kind"] != "program"]
    programs = [c for c in items if c["kind"] == "program"]
    bench_val = benchmark_value(cause)
    bench_measure = benchmark_measure(cause)

    measures = [bench_measure] + sorted({c["measure"] for c in charities} - {bench_measure})
    groups, not_computable = [], []
    for m in measures:
        ranking = calculator.rank_charities(cause, [c for c in charities if c["measure"] == m],
                                            bench_val if m == bench_measure else None)
        for row in ranking["ranked"]:
            _decorate(cause, row)
            if m != bench_measure:
                row["position"] = dict(DIFFERENT_MEASURE)
        not_computable += [_decorate(cause, r) for r in ranking["not_computable"]]
        if ranking["ranked"]:
            groups.append({"measure": m, "measure_label": pres["measures"].get(m, m),
                           "compared_to_benchmark": m == bench_measure, "ranked": ranking["ranked"]})

    prog_rows = calculator.rank_charities(cause, programs, None)
    program_list = [_decorate(cause, r) for r in prog_rows["ranked"] + prog_rows["not_computable"]]
    for r in program_list:
        r.pop("rank", None)
        r.pop("position", None)

    return {
        "cause": cause, "label": spec.label, "metric_label": spec.metric_label,
        "lower_is_better": spec.lower_is_better,
        "explainer": pres["causes"][cause]["explainer"], "caveat": pres["causes"][cause]["caveat"],
        "benchmark": primary_benchmark(cause),
        "benchmark_display": calculator.format_metric(cause, bench_val),
        "benchmark_measure_label": pres["measures"].get(bench_measure, bench_measure),
        "references": [b for b in load()["benchmarks"] if b["cause"] == cause and b.get("role") != "primary"],
        "groups": groups,
        "ranked": [r for g in groups if g["compared_to_benchmark"] for r in g["ranked"]],
        "not_computable": not_computable,
        "programs": program_list,
    }
