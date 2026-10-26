"""FastAPI app: the API plus the static website in web/."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agent as research
from app import calculator, config, data, portfolio

app = FastAPI(title="Charity Impact Tool")
_agent_lock = asyncio.Semaphore(2)   # at most two research runs at once


@app.get("/api/status")
def status():
    used = config.ENV_FILE_USED
    where = None
    if used:
        where = "repo folder" if Path(used).parent == config.ROOT else "folder above the repo"
    return {
        "model": config.MODEL_NAME,
        "has_api_key": config.has_api_key(),          # never the key itself
        "env_file": where,
        "tokens_today": research.tokens_used_today(),
        "daily_token_budget": config.DAILY_TOKEN_BUDGET,
        "prices_per_million": {"input": config.PRICE_PER_M_INPUT,
                               "cached_input": config.PRICE_PER_M_CACHED_INPUT,
                               "output": config.PRICE_PER_M_OUTPUT},
    }


@app.get("/api/causes")
def causes():
    return [{"cause": s.cause, "label": s.label, "metric_label": s.metric_label,
             "lower_is_better": s.lower_is_better,
             "benchmark_display": calculator.format_metric(s.cause, data.benchmark_value(s.cause))}
            for s in calculator.CAUSES.values()]


@app.get("/api/cause/{cause}")
def cause_view(cause: str):
    if cause not in calculator.CAUSES:
        raise HTTPException(404, f"Unknown cause. Use one of: {', '.join(calculator.CAUSES)}.")
    return data.cause_view(cause)


class AnalyzeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    website: str = Field(min_length=4, max_length=300)
    cause: str | None = None


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if req.cause and req.cause not in calculator.CAUSES:
        raise HTTPException(400, "Unknown cause.")
    if not config.has_api_key():
        raise HTTPException(503, "The research agent needs PORTKEY_API_KEY in .env "
                                 "(this folder or the folder above).")
    async with _agent_lock:
        out = await research.analyze_charity(req.name, req.website, req.cause)
    if out.get("result") and out["result"].get("ok"):
        c = out["cause"]
        out["display"] = calculator.format_metric(c, out["result"]["value"])
        out["position"] = calculator.compare_to_benchmark(c, out["result"]["value"],
                                                          data.benchmark_value(c)).to_dict()
        out["benchmark_display"] = calculator.format_metric(c, data.benchmark_value(c))
    return out


@app.post("/api/portfolio")
async def upload_portfolio(file: UploadFile = File(...)):
    raw = await file.read(portfolio.MAX_BYTES + 1)
    try:
        rows = portfolio.parse_csv(raw)
    except portfolio.PortfolioError as e:
        raise HTTPException(400, str(e)) from None
    return await portfolio.assess(rows)


@app.get("/api/ai_safety")
def ai_safety():
    import json
    return json.loads((config.DATA_DIR / "ai_safety.json").read_text(encoding="utf-8"))


@app.get("/api/sample.csv", response_class=PlainTextResponse)
def sample_csv():
    return (config.DATA_DIR / "sample_portfolio.csv").read_text(encoding="utf-8")


@app.get("/")
def index():
    return FileResponse(config.WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=config.WEB_DIR), name="web")
