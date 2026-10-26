"""The benchmark table obeys the sourcing rules."""
from app import calculator, data


def test_one_primary_benchmark_per_cause():
    for cause in calculator.CAUSES:
        prim = [b for b in data.load()["benchmarks"] if b["cause"] == cause and b.get("role") == "primary"]
        assert len(prim) == 1, cause


def test_every_used_number_has_link_date_and_quote():
    d = data.load()
    for item in d["benchmarks"] + d["charities"]:
        if item["status"] == "sourced":
            assert item["source_url"].startswith("http"), item["id"]
            assert item.get("source_date") or item.get("accessed"), item["id"]
            assert item.get("quote"), item["id"]


def test_missing_items_have_no_value_used_and_a_reason():
    d = data.load()
    for b in d["benchmarks"]:
        if b["status"] == "missing":
            assert b.get("missing_reason")
    for c in d["charities"]:
        if c["status"] == "missing":
            view = data.cause_view(c["cause"])
            assert c["id"] in [r["id"] for r in view["not_computable"]]


def test_number_not_in_quote_is_downgraded():
    item = {"id": "x", "status": "sourced", "source_url": "https://e.org", "accessed": "2026-10-26",
            "quote": "It costs about $40 per DALY.", "value": 25}
    assert data._check(item, [25])["status"] == "missing"
    assert data._check(item, [40])["status"] == "sourced"


def test_no_link_is_downgraded():
    item = {"id": "x", "status": "sourced", "source_url": "", "accessed": "2026-10-26",
            "quote": "$40 per DALY", "value": 40}
    out = data._check(item, [40])
    assert out["status"] == "missing" and "no source link" in out["missing_reason"]


def test_percent_implies_base_100():
    item = {"id": "x", "status": "sourced", "source_url": "https://e.org", "accessed": "2026-10-26",
            "quote": "a benefit-cost ratio of 140%"}
    assert data._check(item, [100, 140])["status"] == "sourced"


def test_benchmark_from_inputs_is_computed_in_code():
    b = data.primary_benchmark("education")
    assert b["status"] == "sourced"
    assert abs(b["value"] - 100 / 3) < 1e-9


def test_every_cause_view_builds():
    for cause in calculator.CAUSES:
        v = data.cause_view(cause)
        assert v["benchmark"] is not None
        for r in v["ranked"]:
            assert r["result"]["ok"] and r["result"]["value"] > 0
