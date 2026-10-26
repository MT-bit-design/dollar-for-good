import math

import pytest

from app.calculator import (CAUSES, compare_to_benchmark, compute_metric, format_metric,
                            rank_charities)


# ---- compute_metric: the right formula per cause ----

def test_health_is_cost_per_daly():
    r = compute_metric("health", 5000, 50, "dalys_averted")
    assert r.ok and r.value == pytest.approx(100.0) and r.metric == "usd_per_daly"


def test_poverty_is_income_per_dollar():
    r = compute_metric("poverty", 1, 2.5, "usd_income_gained")
    assert r.ok and r.value == pytest.approx(2.5)


def test_education_is_cost_per_learning_year():
    r = compute_metric("education", 100, 4, "learning_years")
    assert r.ok and r.value == pytest.approx(25.0)


def test_climate_is_cost_per_tonne():
    r = compute_metric("climate", 1_000_000, 50_000, "tco2e_averted")
    assert r.ok and r.value == pytest.approx(20.0)


def test_numeric_strings_are_accepted():
    r = compute_metric("health", "$1,200", "12")
    assert r.ok and r.value == pytest.approx(100.0)


# ---- can't compute: always a reason, never a value ----

@pytest.mark.parametrize("cost,outcome,needle", [
    (None, 10, "Missing cost"),
    (100, None, "Missing outcome"),
    ("abc", 10, "not a number"),
    (100, "lots", "not a number"),
    (True, 10, "not a number"),
    (100, 0, "zero"),
    (0, 10, "zero"),
    (-5, 10, "negative"),
    (math.inf, 10, "finite"),
    (math.nan, 10, "finite"),
])
def test_cannot_compute_gives_reason(cost, outcome, needle):
    r = compute_metric("health", cost, outcome)
    assert not r.ok and r.value is None and needle in r.reason


def test_poverty_zero_cost_cannot_compute():
    r = compute_metric("poverty", 0, 5)
    assert not r.ok and "zero" in r.reason


def test_unknown_cause():
    r = compute_metric("space", 1, 1)
    assert not r.ok and "Unknown cause" in r.reason


def test_wrong_unit_is_rejected():
    r = compute_metric("health", 100, 1, "tco2e_averted")
    assert not r.ok and "needs 'dalys_averted'" in r.reason


# ---- benchmark comparison: higher times_benchmark is always better ----

def test_lower_is_better_comparison():
    p = compare_to_benchmark("health", 50, 100)   # half the cost of the bar
    assert p.ok and p.times_benchmark == pytest.approx(2.0) and p.band == "well_above"


def test_higher_is_better_comparison():
    p = compare_to_benchmark("poverty", 1.5, 3.0)
    assert p.ok and p.times_benchmark == pytest.approx(0.5) and p.band == "below"


def test_band_edges():
    assert compare_to_benchmark("climate", 100, 100).band == "above"
    assert compare_to_benchmark("climate", 400, 100).band == "well_below"


def test_missing_benchmark_means_no_comparison():
    p = compare_to_benchmark("health", 50, None)
    assert not p.ok and "Benchmark is missing" in p.reason


def test_missing_metric_means_no_comparison():
    assert not compare_to_benchmark("health", None, 100).ok


# ---- ranking ----

def _ch(id_, cause, cost, outcome, unit, status="sourced"):
    return {"id": id_, "cause": cause, "status": status,
            "inputs": {"cost_usd": cost, "outcome_amount": outcome, "outcome_unit": unit}}


def test_rank_lower_is_better_puts_cheapest_first():
    chs = [_ch("a", "health", 300, 1, "dalys_averted"),
           _ch("b", "health", 100, 1, "dalys_averted"),
           _ch("c", "health", 200, 1, "dalys_averted")]
    out = rank_charities("health", chs, 150)
    assert [r["id"] for r in out["ranked"]] == ["b", "c", "a"]
    assert [r["rank"] for r in out["ranked"]] == [1, 2, 3]


def test_rank_higher_is_better_puts_biggest_first():
    chs = [_ch("a", "poverty", 1, 1.2, "usd_income_gained"),
           _ch("b", "poverty", 1, 3.0, "usd_income_gained")]
    out = rank_charities("poverty", chs, 2.0)
    assert [r["id"] for r in out["ranked"]] == ["b", "a"]


def test_missing_charity_is_listed_not_ranked():
    chs = [_ch("a", "health", 100, 1, "dalys_averted"),
           _ch("m", "health", 999, 1, "dalys_averted", status="missing")]
    out = rank_charities("health", chs, 150)
    assert [r["id"] for r in out["ranked"]] == ["a"]
    assert out["not_computable"][0]["id"] == "m"
    assert out["not_computable"][0]["result"]["reason"]


def test_rank_filters_other_causes():
    chs = [_ch("a", "health", 100, 1, "dalys_averted"),
           _ch("x", "climate", 10, 1, "tco2e_averted")]
    out = rank_charities("health", chs, None)
    assert [r["id"] for r in out["ranked"]] == ["a"]
    assert not out["ranked"][0]["position"]["ok"]   # benchmark missing -> no comparison


def test_format_metric():
    assert format_metric("poverty", 2.5) == "$2.50 per $1"
    assert format_metric("health", 1234.4) == "$1,234"
    assert format_metric("health", None) == "can't compute"


def test_every_cause_has_a_spec():
    assert set(CAUSES) == {"health", "poverty", "education", "climate"}
