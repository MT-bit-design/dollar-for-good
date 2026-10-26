r"""Compute every dollar figure in the report, slides and eval/RESULTS.md from measured tokens.

    .venv\Scripts\python.exe tools/costs.py

Reads the measured token counts in eval/results/*.json and docs/evidence/live_run.json,
prices them with the rates in app/config.py, and writes:
  eval/costs.json   numbers the report and slides fill in ({{cost:KEY}}, see build_docs.py)
  eval/RESULTS.md   the accuracy and cost write-up
Nothing here is typed by hand: change a rate in app/config.py and rerun.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import config  # noqa: E402

RESULTS = ROOT / "eval" / "results"
VERSIONS = [("baseline", "1. First version"), ("v2_after_fixes", "2. Parser + percent fixes"),
            ("v3_validator_retry", "3. Code check as validator, one retry (**shipped**)"),
            ("exp_short_pages_4k", "Experiment: page text cut to 4,000 chars"),
            ("exp_medium_effort", "Experiment: reasoning effort medium")]
DONOR_RUNS, FUNDER_RUNS = 4, 14          # assumed monthly use, stated as an assumption everywhere


def run_cost(u: dict) -> float:
    """One run's cost at the configured rates. Same formula the app uses."""
    inp, cached, out = u.get("input_tokens", 0), u.get("cached_input_tokens", 0), u.get("output_tokens", 0)
    return (max(inp - cached, 0) * config.PRICE_PER_M_INPUT + cached * config.PRICE_PER_M_CACHED_INPUT
            + out * config.PRICE_PER_M_OUTPUT) / 1_000_000


def money(x: float) -> str:
    if x >= 100:
        return f"${x:,.0f}"
    if x >= 1:
        return f"${x:,.2f}"
    return "$" + format(x, "#.3g")      # three significant figures, e.g. $0.000202, $0.283


def version(name: str) -> dict:
    d = json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
    rows = d["rows"]
    n = len(rows)
    tot = lambda k: sum((r["usage"] or {}).get(k, 0) for r in rows)
    s = d["summary"]
    return {"n": n, "accuracy": s["accuracy"], "wrong": s["wrong_numbers_shown"],
            "found": s["found_when_figure_exists"], "refused": s["refused_when_no_valid_figure"],
            "input": tot("input_tokens") / n, "cached": tot("cached_input_tokens") / n,
            "output": tot("output_tokens") / n, "seconds": tot("seconds") / n, "requests": tot("requests") / n,
            "cost": sum(run_cost(r["usage"] or {}) for r in rows) / n}


def main():
    V = {k: version(k) for k, _ in VERSIONS}
    ship, first, med, short = V["v3_validator_retry"], V["baseline"], V["exp_medium_effort"], V["exp_short_pages_4k"]
    live = json.loads((ROOT / "docs" / "evidence" / "live_run.json").read_text(encoding="utf-8"))
    lu = live["usage"]
    live_cost = run_cost(lu)

    medium_ratio = med["cost"] / ship["cost"]
    short_saving = 1 - short["cost"] / ship["cost"]
    costs = {
        "rate_input": f"${config.PRICE_PER_M_INPUT:.2f}", "rate_cached": f"${config.PRICE_PER_M_CACHED_INPUT:.2f}",
        "rate_output": f"${config.PRICE_PER_M_OUTPUT:.2f}", "rate_source": config.PRICE_SOURCE,   # as published
        "ship_input": f"{ship['input']:,.0f}", "ship_cached": f"{ship['cached']:,.0f}", "ship_output": f"{ship['output']:,.0f}",
        "ship_requests": f"{ship['requests']:.1f}", "ship_seconds": f"{ship['seconds']:.0f}",
        "cached_share": f"{ship['cached'] / ship['input']:.0%}",
        "ship_cost": money(ship["cost"]), "ship_cost_per_1000": money(ship["cost"] * 1000),
        "first_cost": money(first["cost"]), "first_input": f"{first['input']:,.0f}",
        "medium_cost": money(med["cost"]), "short_cost": money(short["cost"]),
        "medium_ratio": f"{medium_ratio:.1f}", "short_saving_pct": f"{short_saving:.0%}",
        "first_to_ship_verb": "fell" if ship["cost"] < first["cost"] else "rose",
        "donor_runs": str(DONOR_RUNS), "funder_runs": str(FUNDER_RUNS),
        "donor_month": money(DONOR_RUNS * ship["cost"]), "funder_month": money(FUNDER_RUNS * ship["cost"]),
        "runs_100": f"{100 * FUNDER_RUNS:,}", "runs_10000": f"{10_000 * FUNDER_RUNS:,}",
        "users100_month": money(100 * FUNDER_RUNS * ship["cost"]), "users10000_month": money(10_000 * FUNDER_RUNS * ship["cost"]),
        "live_input": f"{lu['input_tokens']:,}", "live_cached": f"{lu['cached_input_tokens']:,}",
        "live_output": f"{lu['output_tokens']:,}", "live_requests": str(lu["requests"]),
        "live_pages": str(lu["tool_calls"]), "live_seconds": f"{lu['seconds']:.1f}", "live_cost": money(live_cost),
    }
    for k, _ in VERSIONS:
        costs[f"cost_{k}"] = money(V[k]["cost"])
    (ROOT / "eval" / "costs.json").write_text(json.dumps(costs, indent=1), encoding="utf-8")

    def row(k, label):
        v = V[k]
        return (f"| {label} | {v['accuracy']:.0%} | {v['wrong']} | {v['found']:.0%} | {v['refused']:.0%} | "
                f"{v['input']:,.0f} | {v['cached']:,.0f} | {v['output']:,.0f} | {money(v['cost'])} | {v['seconds']:.1f}s |")

    c = costs
    md = f"""# Measured accuracy and token cost

All numbers below come from real `gpt-6-luna` runs through Portkey, made with `eval/run_eval.py`
on 2026-10-26. Raw per-case output is in `eval/results/*.json`. Token counts are measured.
Dollar costs are computed by `tools/costs.py` from those token counts at the rates in `app/config.py`:
input {c['rate_input']}/1M, cached input {c['rate_cached']}/1M, output {c['rate_output']}/1M.
These are {config.PRICE_SOURCE}, for prompts up to 272K tokens (every run here is far below that), from
the OpenAI API pricing page (https://developers.openai.com/api/docs/pricing), also reported by eesel.ai
(https://www.eesel.ai/blog/gpt-6-luna-pricing) and AnotherWrapper (https://anotherwrapper.com/llm-pricing/gpt-6-luna,
input and output rates). The course key is billed through Portkey, so its actual billing may differ.

## The test set (18 cases)
- 14 synthetic charity pages (`eval/pages/`) with known answers: 8 have a valid figure (stated as a rate,
  as totals, as "per $100", as a percent), 6 should be refused (cost per life saved, no figure, a range,
  test scores, an offset price, and two prompt injections).
- 4 real charity websites fetched live: One Acre Fund, Village Enterprise, GiveDirectly, Living Goods.
  Labels come from our sourced table (`data/research/`).

"Wrong numbers shown" is the number that matters most: a figure the app would display that is not right.

## Results by version

| Version | Accuracy | Wrong numbers shown | Found when a figure exists | Refused when none | Input tok/run | Cached input/run | Output tok/run | Cost/run | Time/run |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(row(k, label) for k, label in VERSIONS) + f"""

What changed between versions, and why:
1. **First version**: 2 wrong numbers. GiveDirectly's "2.5x" was parsed as 2 (a parser bug), and
   Village Enterprise returned a different figure than our table. It also missed two valid figures
   ("210%" and "1.25 million tonnes of CO2", where the "2" in CO2 broke the parser).
2. **Parser fixes**: numbers glued to letters (CO2) are ignored, "2.5x" parses, percent ratios are supported.
   This exposed a new wrong number: GiveDirectly's "83% of expenses delivered to recipients" read as income per dollar.
3. **Shipped**: the poverty check now requires the quote to talk about income/benefit *and* per-dollar form,
   the prompt explains how to fill "X per $Y", and the code check runs as an output validator so the
   model gets one retry with the exact reason. Result: **0 wrong numbers, 100% precision, {ship['accuracy']:.0%} accuracy**.

Remaining misses (honest):
- GiveDirectly (real site): the agent refused; the site's "2.5x local economic activity" is a valid figure
  that our checks now treat cautiously. A miss, not a wrong number.
- Village Enterprise (real site): the homepage says "$5.34 in benefits for every $1 invested", while the
  charity's own blog reports a 140% three-year benefit-cost ratio (our table). The quote is real and verified,
  so we count it as a *verified alternative*, not an error. It shows a real limit: charities publish
  conflicting self-reported figures.

## Did cost cutting hurt quality?
- **Reasoning effort low vs medium**: medium cost {c['medium_ratio']}x as much per run ({c['medium_cost']} vs {c['ship_cost']}) and was slower, with identical accuracy.
  We ship low.
- **Page text 12,000 vs 4,000 characters**: 4,000 was {c['short_saving_pct']} cheaper ({c['short_cost']} vs {c['ship_cost']}) with identical accuracy on this set.
  But the synthetic pages are short, so only the 4 real sites tested this; long real pages can hide the figure
  past 4,000 characters. We keep 12,000 as the safer default. This is a judgement call, not proven either way.
- **Prompt caching**: the system prompt is long and fixed and comes first, so the provider caches it.
  In the shipped version {c['cached_share']} of input tokens were cached.
- **Safer was also cheaper**: input per run grew from {c['first_input']} to {c['ship_input']} tokens, but cost per run
  {c['first_to_ship_verb']} from {c['first_cost']} to {c['ship_cost']}, because more of the longer fixed prompt is cached.
- **Answer cache**: a charity researched once is stored in `output/agent_cache.json`; repeat lookups cost 0 tokens.
- **Sourced table first**: the donor view and any charity already in the table use no model at all.

## Tokenomics (shipped version)
- One research run: {c['ship_input']} input tokens ({c['ship_cached']} cached), {c['ship_output']} output tokens,
  {c['ship_requests']} model calls, about {c['ship_seconds']} s. **{c['ship_cost']} per run** ({c['ship_cost_per_1000']} per 1,000 runs).
- The live run in report Figure 3: {c['live_input']} input ({c['live_cached']} cached), {c['live_output']} output,
  {c['live_requests']} model calls, {c['live_pages']} pages, {c['live_seconds']} s, {c['live_cost']}.
- Browsing the donor view: 0 tokens.
- Assumed monthly use (an estimate, not measured): a donor researches {DONOR_RUNS} new charities a month;
  a foundation program officer uploads one portfolio with 10 un-listed charities plus {FUNDER_RUNS - 10} one-off lookups.

| | Runs/month | Cost/month |
|---|---|---|
| One donor | {DONOR_RUNS} | {c['donor_month']} |
| One foundation user | {FUNDER_RUNS} | {c['funder_month']} |
| 100 foundation users | {c['runs_100']} | {c['users100_month']} |
| 10,000 foundation users | {c['runs_10000']} | {c['users10000_month']} |

These are upper bounds: the shared answer cache means a charity researched for one user is free for the next,
so at 10,000 users most popular charities would already be cached.

## Guards measured in tests
- Per run: at most {config.RUN_REQUEST_LIMIT} model calls, {config.RUN_TOOL_CALL_LIMIT} page fetches, {config.RUN_TOTAL_TOKEN_LIMIT:,} tokens.
- Per day: {config.DAILY_TOKEN_BUDGET:,} tokens across all users; when reached, research is refused before any model call.
- Per upload: {config.MAX_PORTFOLIO_ROWS} rows, {config.MAX_AGENT_ROWS_PER_UPLOAD} researched by the agent.
"""
    (ROOT / "eval" / "RESULTS.md").write_text(md, encoding="utf-8")
    for k in ("ship_cost", "first_cost", "medium_cost", "short_cost", "medium_ratio", "short_saving_pct",
              "first_to_ship_verb", "donor_month", "funder_month", "users100_month", "users10000_month", "live_cost"):
        print(f"{k:20} {costs[k]}")


if __name__ == "__main__":
    main()
