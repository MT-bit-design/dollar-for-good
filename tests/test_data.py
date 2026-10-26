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
            listed = [r["id"] for r in view["not_computable"] + view["programs"]]
            assert c["id"] in listed
            assert c["id"] not in [r["id"] for g in view["groups"] for r in g["ranked"]]


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


# ---- plain words, one measure per ranking, program types apart

import re

FIRST_PERSON = re.compile(r"(I|me|my|we|our|us)", re.I)


def test_each_ranking_uses_one_measure_and_only_that_group_meets_the_benchmark():
    for cause in calculator.CAUSES:
        v = data.cause_view(cause)
        for g in v["groups"]:
            assert {r["measure"] for r in g["ranked"]} == {g["measure"]}
            for r in g["ranked"]:
                assert r["position"]["ok"] is g["compared_to_benchmark"] or not data.benchmark_value(cause)


def test_education_measures_are_not_mixed():
    v = data.cause_view("education")
    measures = [g["measure"] for g in v["groups"]]
    assert measures[0] == "lays" and len(measures) == len(set(measures))
    camfed = [r for g in v["groups"] for r in g["ranked"] if r["id"] == "camfed_tanzania"]
    assert camfed and not camfed[0]["position"]["ok"]


def test_program_types_are_listed_apart_and_never_ranked():
    v = data.cause_view("education")
    names = [p["name"] for p in v["programs"]]
    assert "School-based deworming (general estimate)" in names
    ranked_ids = [r["id"] for g in v["groups"] for r in g["ranked"]]
    assert "deworm_the_world" not in ranked_ids
    assert all("rank" not in p for p in v["programs"])


def test_donor_notes_are_plain_sentences():
    for cause in calculator.CAUSES:
        v = data.cause_view(cause)
        for r in v["not_computable"] + [p for p in v["programs"] if not p["result"]["ok"]]:
            note = r["donor_note"]
            assert note.endswith(".") and note.count(".") == 1, note
            assert not FIRST_PERSON.search(note), note
            assert not re.search(r"\d", note), note
            assert "HTTP" not in note and "MISSING" not in note, note


def test_cause_explainers_exist_and_are_plain():
    for cause in calculator.CAUSES:
        v = data.cause_view(cause)
        assert v["explainer"] and not FIRST_PERSON.search(v["explainer"])
        assert not FIRST_PERSON.search(v["caveat"])


def test_agent_plain_reasons_have_no_jargon():
    from app.agent import plain_reason
    cases = [
        {"status": "budget"}, {"status": "error", "reason": "HTTPError 500"},
        {"status": "not_computable", "reason": "That page contains text aimed at manipulating an AI",
         "extraction": {"found": True}},
        {"status": "not_computable", "reason": "I saw $68 per life-year saved", "extraction": {"found": False}},
        {"status": "not_computable", "reason": "The quote does not appear word for word", "extraction": {"found": True}},
    ]
    for c in cases:
        txt = plain_reason(c)
        assert txt and not FIRST_PERSON.search(txt) and not re.search(r"\d|HTTP", txt), txt
    assert plain_reason({"status": "computed"}) is None


def test_ranges_are_only_shown_when_sourced():
    for c in data.load()["charities"]:
        if c.get("range"):
            assert c["status"] == "sourced" and c["range"]["quote"]
            assert c["range"]["low"] <= c["range"]["high"]
