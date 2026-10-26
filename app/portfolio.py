"""Philanthropy view: read a funder's CSV and place each charity against its benchmark."""

from __future__ import annotations

import asyncio
import csv
import io
import re

from app import agent as research
from app import calculator, config, data
from app.fetch import normalize

COLUMNS = ["name", "cause", "website", "amount_granted_usd", "cost_usd", "outcome_amount"]
MAX_BYTES = 200_000

CAUSE_ALIASES = {
    "health": "health", "global health": "health",
    "poverty": "poverty", "cash": "poverty", "cash transfers": "poverty",
    "poverty and cash transfers": "poverty", "income": "poverty",
    "education": "education", "learning": "education",
    "climate": "climate", "climate change": "climate", "carbon": "climate",
}


class PortfolioError(ValueError):
    pass


def _key(name: str) -> str:
    name = re.sub(r"\(.*?\)", "", name)          # "Youth Impact (ConnectEd)" -> "Youth Impact"
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _cell(s: str | None, limit: int = 200) -> str:
    return normalize(s or "")[:limit]


def parse_csv(raw: bytes) -> list[dict]:
    if len(raw) > MAX_BYTES:
        raise PortfolioError(f"File is too large (limit {MAX_BYTES // 1000} KB).")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise PortfolioError("File must be a UTF-8 CSV.") from None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise PortfolioError("The file is empty.")
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}
    if "name" not in fields:
        raise PortfolioError("The CSV needs a 'name' column. Columns: " + ", ".join(COLUMNS))
    rows = []
    for i, r in enumerate(reader, start=1):
        if i > config.MAX_PORTFOLIO_ROWS:
            raise PortfolioError(f"Too many rows (limit {config.MAX_PORTFOLIO_ROWS}).")
        row = {c: _cell(r.get(fields[c])) if c in fields else "" for c in COLUMNS}
        if not row["name"]:
            continue
        rows.append(row)
    if not rows:
        raise PortfolioError("No charities found in the file.")
    return rows


def _curated_match(name: str, cause: str | None) -> dict | None:
    k = _key(name)
    for c in data.load()["charities"]:
        if (cause is None or c["cause"] == cause) and k and (k == _key(c["name"]) or k == _key(c["id"])):
            return c
    return None


async def assess_row(row: dict, allow_agent: bool, sem: asyncio.Semaphore) -> dict:
    cause = CAUSE_ALIASES.get(row["cause"].lower()) if row["cause"] else None
    out = {"name": row["name"], "cause_input": row["cause"], "cause": cause, "website": row["website"],
           "amount_granted_usd": calculator._as_number(row["amount_granted_usd"])}

    def finish(cause_, res, source, extra=None):
        out["cause"] = cause_
        out["result"] = res.to_dict()
        out["data_source"] = source
        if extra:
            out.update(extra)
        if res.ok:
            out["display"] = calculator.format_metric(cause_, res.value)
            out["position"] = calculator.compare_to_benchmark(
                cause_, res.value, data.benchmark_value(cause_)).to_dict()
        else:
            out.setdefault("donor_note", res.reason)
        return out

    # 1. Numbers in the funder's own file come first.
    if row["cost_usd"] or row["outcome_amount"]:
        if cause is None:
            return finish(None, calculator.MetricResult(False, None, None,
                          "Your numbers can't be used without a cause."), "your_file")
        res = calculator.compute_metric(cause, row["cost_usd"] or None, row["outcome_amount"] or None)
        return finish(cause, res, "your_file")

    # 2. A charity already in the sourced table.
    cur = _curated_match(row["name"], cause)
    if cur:
        inp = cur.get("inputs") or {}
        if cur["status"] == "sourced":
            res = calculator.compute_metric(cur["cause"], inp.get("cost_usd"), inp.get("outcome_amount"),
                                            inp.get("outcome_unit"))
        else:
            res = calculator.MetricResult(False, None, None, cur.get("missing_reason") or "No sourced figure.")
        if cur["status"] != "sourced":
            out["donor_note"] = cur.get("donor_note") or "No published estimate in this cause's measure was found."
        finish(cur["cause"], res, "sourced_table",
               {"source_url": cur.get("source_url"), "source_date": cur.get("source_date"),
                "quote": cur.get("quote"), "range_display": (cur.get("range") or {}).get("display")})
        if res.ok and not data.comparable(cur):
            out["position"] = dict(data.DIFFERENT_MEASURE)
        return out

    # 3. Ask the research agent, if there is a website and budget.
    if not row["website"]:
        return finish(cause, calculator.MetricResult(False, None, None,
                      "Not in the sourced table and no website was given, so there is nothing to look up."), "none")
    if not allow_agent:
        out["donor_note"] = "Skipped because each upload looks up a limited number of new charities."
        return finish(cause, calculator.MetricResult(False, None, None,
                      f"Skipped: only {config.MAX_AGENT_ROWS_PER_UPLOAD} rows per upload are researched."), "none")
    if not config.has_api_key():
        return finish(cause, calculator.MetricResult(False, None, None,
                      "The research assistant is switched off because no API key is set."), "none")
    async with sem:
        r = await research.analyze_charity(row["name"], row["website"], cause)
    cause_ = r.get("cause") or cause
    extra = {"agent": {k: r.get(k) for k in ("status", "reason", "trace", "usage", "cached",
                                             "suspicious_instructions_seen")},
             "source_url": (r.get("extraction") or {}).get("source_url"),
             "quote": (r.get("extraction") or {}).get("quote")}
    if r.get("donor_reason"):
        out["donor_note"] = r["donor_reason"]
    if r.get("status") == "computed":
        res = calculator.MetricResult(**r["result"])
    else:
        res = calculator.MetricResult(False, None, None, r.get("reason") or "Research found no figure.")
    if cause_ not in calculator.CAUSES:
        return finish(None, calculator.MetricResult(False, None, None, res.reason or "Unknown cause."),
                      "agent", extra)
    return finish(cause_, res, "agent", extra)


async def assess(rows: list[dict]) -> dict:
    sem = asyncio.Semaphore(3)
    needs_agent = 0
    tasks = []
    for row in rows:
        has_numbers = bool(row["cost_usd"] or row["outcome_amount"])
        cause = CAUSE_ALIASES.get(row["cause"].lower()) if row["cause"] else None
        will_need = not has_numbers and not _curated_match(row["name"], cause) and bool(row["website"])
        allow = True
        if will_need:
            needs_agent += 1
            allow = needs_agent <= config.MAX_AGENT_ROWS_PER_UPLOAD
        tasks.append(assess_row(row, allow, sem))
    results = await asyncio.gather(*tasks)
    return {"rows": list(results), "summary": summarize(results)}


def summarize(rows: list[dict]) -> dict:
    computed = [r for r in rows if r["result"]["ok"]]
    compared = [r for r in computed if (r.get("position") or {}).get("ok")]
    above = [r for r in compared if r["position"]["times_benchmark"] >= 1]
    total = sum(r["amount_granted_usd"] or 0 for r in rows)
    above_amt = sum(r["amount_granted_usd"] or 0 for r in above)
    tokens = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for r in rows:
        u = ((r.get("agent") or {}).get("usage")) or {}
        if (r.get("agent") or {}).get("cached"):
            continue
        for k in tokens:
            tokens[k] += u.get(k, 0) or 0
    return {
        "charities": len(rows), "computed": len(computed), "not_computable": len(rows) - len(computed),
        "compared": len(compared), "at_or_above_benchmark": len(above),
        "granted_total_usd": total, "granted_at_or_above_usd": above_amt,
        "share_of_dollars_at_or_above": (above_amt / total) if total else None,
        "tokens": {**tokens, "cost_usd": round(tokens["cost_usd"], 6)},
    }
