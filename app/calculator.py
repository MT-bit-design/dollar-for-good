"""All impact math lives here, in plain Python. The model never computes a number.

Every function is pure: no I/O, no network, no model. A charity that cannot be
computed gets a reason, never a guessed value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Iterable


@dataclass(frozen=True)
class CauseSpec:
    cause: str
    label: str
    metric: str           # unit id of the result, e.g. "usd_per_daly"
    metric_label: str     # what the donor sees
    outcome_unit: str     # unit the outcome input must be in
    lower_is_better: bool


CAUSES: dict[str, CauseSpec] = {
    "health": CauseSpec("health", "Health", "usd_per_daly",
                        "Cost per DALY averted (USD)", "dalys_averted", True),
    "poverty": CauseSpec("poverty", "Poverty and cash transfers", "usd_income_per_usd",
                         "Income gained per dollar (USD)", "usd_income_gained", False),
    "education": CauseSpec("education", "Education", "usd_per_learning_year",
                           "Cost per extra year of learning (USD)", "learning_years", True),
    "climate": CauseSpec("climate", "Climate", "usd_per_tco2e",
                         "Cost per tonne CO2e averted (USD)", "tco2e_averted", True),
}


@dataclass(frozen=True)
class MetricResult:
    ok: bool
    value: float | None
    metric: str | None
    reason: str | None = None   # set whenever ok is False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fail(reason: str, metric: str | None = None) -> MetricResult:
    return MetricResult(ok=False, value=None, metric=metric, reason=reason)


def _as_number(x: Any) -> float | None:
    """Accept ints/floats (not bools) and clean numeric strings like "1,234.5". Else None."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "").replace("$", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def compute_metric(cause: str, cost_usd: Any, outcome_amount: Any,
                   outcome_unit: str | None = None) -> MetricResult:
    """Return the cause's metric from cost and outcome, or a reason it can't be computed."""
    spec = CAUSES.get(cause)
    if spec is None:
        return _fail(f"Unknown cause '{cause}'. Use one of: {', '.join(CAUSES)}.")
    m = spec.metric
    if outcome_unit is not None and outcome_unit != spec.outcome_unit:
        return _fail(f"Outcome is in '{outcome_unit}', but {spec.label} needs '{spec.outcome_unit}'.", m)

    if cost_usd is None:
        return _fail("Missing cost (USD).", m)
    if outcome_amount is None:
        return _fail(f"Missing outcome ({spec.outcome_unit}).", m)
    cost = _as_number(cost_usd)
    outcome = _as_number(outcome_amount)
    if cost is None:
        return _fail(f"Cost is not a number: {cost_usd!r}.", m)
    if outcome is None:
        return _fail(f"Outcome is not a number: {outcome_amount!r}.", m)
    if not (math.isfinite(cost) and math.isfinite(outcome)):
        return _fail("Cost or outcome is not a finite number.", m)
    if cost < 0 or outcome < 0:
        return _fail("Cost and outcome must not be negative.", m)

    if spec.lower_is_better:   # cost per unit of good
        if outcome == 0:
            return _fail("Outcome is zero, so cost per unit is undefined.", m)
        if cost == 0:
            return _fail("Cost is zero, so cost per unit is not meaningful.", m)
        value = cost / outcome
    else:                      # good per dollar
        if cost == 0:
            return _fail("Cost is zero, so good per dollar is undefined.", m)
        value = outcome / cost
    return MetricResult(ok=True, value=value, metric=m)


@dataclass(frozen=True)
class Position:
    ok: bool
    times_benchmark: float | None   # >1 means more good per dollar than the benchmark
    band: str | None                # "well_above" | "above" | "below" | "well_below"
    label: str | None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_to_benchmark(cause: str, value: float | None, benchmark_value: float | None) -> Position:
    """How many times as much good per dollar as the benchmark (higher is always better)."""
    spec = CAUSES.get(cause)
    if spec is None:
        return Position(False, None, None, None, f"Unknown cause '{cause}'.")
    if value is None:
        return Position(False, None, None, None, "Charity metric could not be computed.")
    if benchmark_value is None:
        return Position(False, None, None, None, "Benchmark is missing (no source), so no comparison.")
    if value <= 0 or benchmark_value <= 0:
        return Position(False, None, None, None, "Metric and benchmark must be positive to compare.")

    times = benchmark_value / value if spec.lower_is_better else value / benchmark_value
    if times >= 2:
        band, label = "well_above", f"{times:.1f}x the benchmark"
    elif times >= 1:
        band, label = "above", f"{times:.2f}x the benchmark"
    elif times >= 0.5:
        band, label = "below", f"{times:.2f}x the benchmark"
    else:
        band, label = "well_below", f"{times:.2f}x the benchmark"
    return Position(True, times, band, label)


def rank_charities(cause: str, charities: Iterable[dict], benchmark_value: float | None) -> dict[str, list[dict]]:
    """Split charities into ranked (best first) and not_computable (with reasons).

    Each charity dict needs "inputs": {"cost_usd", "outcome_amount", "outcome_unit"}.
    Charities whose data status is "missing" are never computed.
    """
    spec = CAUSES[cause]
    ranked, not_computable = [], []
    for ch in charities:
        if ch.get("cause") != cause:
            continue
        inputs = ch.get("inputs") or {}
        if ch.get("status") == "missing":
            res = _fail(ch.get("missing_reason") or "No sourced numbers for this charity.", spec.metric)
        else:
            res = compute_metric(cause, inputs.get("cost_usd"), inputs.get("outcome_amount"),
                                 inputs.get("outcome_unit"))
        row = {**ch, "result": res.to_dict()}
        if res.ok:
            row["position"] = compare_to_benchmark(cause, res.value, benchmark_value).to_dict()
            ranked.append(row)
        else:
            not_computable.append(row)
    ranked.sort(key=lambda r: r["result"]["value"], reverse=not spec.lower_is_better)
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"ranked": ranked, "not_computable": not_computable}


def format_metric(cause: str, value: float | None) -> str:
    """Human display only. Never feed this back into math."""
    if value is None:
        return "can't compute"
    if CAUSES[cause].metric == "usd_income_per_usd":
        return f"${value:,.2f} per $1"
    return f"${value:,.0f}" if value >= 100 else f"${value:,.2f}"
