"""Measure the research agent's accuracy and token cost on the labelled set.

    .venv\\Scripts\\python.exe -m eval.run_eval --name baseline
    .venv\\Scripts\\python.exe -m eval.run_eval --name short_pages --page-limit 4000
    .venv\\Scripts\\python.exe -m eval.run_eval --name medium_effort --effort medium

Writes eval/results/<name>.json. Uses real gpt-6-luna calls (costs tokens). No cache.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from app import agent as research
from app import config, fetch
from app.fetch import Page, clean_text

HERE = Path(__file__).parent
TOL = 0.01   # relative tolerance when comparing a computed value with the label


def matches(value, accept) -> bool:
    return value is not None and any(abs(value - a) <= TOL * abs(a) for a in accept)


def serve_synthetic():
    real_fetch = fetch.fetch_page

    def fake(url, website=None, **kw):
        host = url.split("//", 1)[-1].split("/", 1)[0]
        if host.endswith(".eval.test"):
            case = host.removesuffix(".eval.test")
            path = HERE / "pages" / f"{case}.html"
            if url.rstrip("/") != f"https://{host}" or not path.exists():
                raise fetch.FetchError("The site answered with HTTP 404.")
            text = clean_text(path.read_text(encoding="utf-8"))
            return Page(url=url, text=text[: config.PAGE_TEXT_LIMIT], truncated=len(text) > config.PAGE_TEXT_LIMIT)
        return real_fetch(url, website, **kw)
    fetch.fetch_page = fake


async def one(case: dict, synthetic: bool) -> dict:
    website = f"https://{case['id']}.eval.test" if synthetic else case["website"]
    out = await research.analyze_charity(case["name"], website, case["cause"], use_cache=False)
    value = (out.get("result") or {}).get("value") if out.get("status") == "computed" else None
    accept = ([case["expect"]] if case["expect"] is not None else []) if synthetic else case["accept"]
    if accept:
        verdict = "correct" if matches(value, accept) else ("wrong_value" if value is not None else "missed")
        if verdict == "wrong_value" and matches(value, case.get("also_on_site", [])):
            verdict = "verified_alternative"   # real quote, but a different figure than our table
    else:
        verdict = "correct_refusal" if value is None else "false_figure"
    return {"id": case["id"], "set": "synthetic" if synthetic else "real", "cause": case["cause"],
            "expected": accept or None, "got": value, "status": out.get("status"),
            "reason": out.get("reason"), "verdict": verdict, "usage": out.get("usage"),
            "flagged": out.get("suspicious_instructions_seen"),
            "quote": (out.get("extraction") or {}).get("quote")}


def summarize(rows: list[dict]) -> dict:
    def tot(k):
        return sum((r["usage"] or {}).get(k, 0) for r in rows)
    n = len(rows)
    has_fig = [r for r in rows if r["expected"]]
    no_fig = [r for r in rows if not r["expected"]]
    computed = [r for r in rows if r["got"] is not None]
    return {
        "cases": n,
        "accuracy": sum(r["verdict"] in ("correct", "correct_refusal") for r in rows) / n,
        "found_when_figure_exists": sum(r["verdict"] == "correct" for r in has_fig) / max(1, len(has_fig)),
        "refused_when_no_valid_figure": sum(r["verdict"] == "correct_refusal" for r in no_fig) / max(1, len(no_fig)),
        "wrong_numbers_shown": sum(r["verdict"] in ("wrong_value", "false_figure") for r in rows),
        "verified_alternative": sum(r["verdict"] == "verified_alternative" for r in rows),
        "precision_of_shown_numbers": (sum(r["verdict"] in ("correct", "verified_alternative") for r in computed)
                                       / len(computed)) if computed else None,
        "tokens": {"input": tot("input_tokens"), "cached_input": tot("cached_input_tokens"),
                   "output": tot("output_tokens")},
        "per_run_avg": {"input": tot("input_tokens") / n, "cached_input": tot("cached_input_tokens") / n,
                        "output": tot("output_tokens") / n, "cost_usd": tot("cost_usd") / n,
                        "seconds": tot("seconds") / n, "requests": tot("requests") / n},
        "total_cost_usd": tot("cost_usd"),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="baseline")
    ap.add_argument("--effort", default=config.REASONING_EFFORT)
    ap.add_argument("--page-limit", type=int, default=config.PAGE_TEXT_LIMIT)
    ap.add_argument("--only", choices=["synthetic", "real"], default=None)
    args = ap.parse_args()

    config.REASONING_EFFORT = args.effort
    config.PAGE_TEXT_LIMIT = args.page_limit
    research._agent = None
    serve_synthetic()

    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))
    jobs = []
    if args.only != "real":
        jobs += [(c, True) for c in labels["synthetic"]]
    if args.only != "synthetic":
        jobs += [(c, False) for c in labels["real"]]

    sem = asyncio.Semaphore(4)

    async def guarded(c, s):
        async with sem:
            return await one(c, s)
    t0 = time.time()
    rows = await asyncio.gather(*(guarded(c, s) for c, s in jobs))
    result = {"name": args.name, "model": config.MODEL_NAME, "effort": args.effort,
              "page_limit": args.page_limit, "wall_seconds": round(time.time() - t0, 1),
              "summary": summarize(rows),
              "summary_synthetic": summarize([r for r in rows if r["set"] == "synthetic"]) if args.only != "real" else None,
              "summary_real": summarize([r for r in rows if r["set"] == "real"]) if args.only != "synthetic" else None,
              "rows": rows}
    out = HERE / "results" / f"{args.name}.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['verdict']:16} {r['id']:20} expected={r['expected']} got={r['got']}  {(r['reason'] or '')[:90]}")
    print(json.dumps(result["summary"], indent=1))
    print("saved", out)


if __name__ == "__main__":
    asyncio.run(main())
