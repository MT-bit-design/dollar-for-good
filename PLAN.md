# Plan: Charity Impact Tool

## One line
A donor picks a cause and sees charities ranked by how much good each dollar does, in the right unit for that cause. A philanthropy view lets a funder upload the charities they fund and see where each one sits against its cause benchmark.

## The four causes and their units

| Cause | Metric | Formula (plain code) | Better is |
|---|---|---|---|
| Health | Cost per DALY averted | cost_usd / dalys_averted | lower |
| Poverty and cash transfers | Income gained per dollar | income_gain_usd / cost_usd | higher |
| Education | Cost per extra year of learning (LAYS) | cost_usd / learning_years | lower |
| Climate | Cost per tonne CO2e averted | cost_usd / tonnes_co2e | lower |

## Hard rules (from Michael + the assignment)
1. Every benchmark and charity number has a source URL, a source date, and an accessed date. No source = `status: "missing"`, value `null`. Never guess.
2. All math is plain Python in `app/calculator.py`. The model never computes a number.
3. If a charity can't be computed (missing input, zero denominator, wrong unit), the app says so and why. It is listed, not ranked.
4. All website text is untrusted data. It is fenced, never followed, and any number the agent extracts must appear verbatim in the page text or it is rejected.
5. Never commit `.env`; never print or log an API key. `.env` is read from the repo folder first, then the folder above it.
6. Course key only: `PORTKEY_API_KEY` with `gpt-6-luna`.
7. Work only inside `final project/`.

## Architecture
- `data/benchmarks.json`: one benchmark per cause (plus reference points), each with source + dates.
- `data/charities.json`: curated charities with sourced inputs (cost, outcome) and a verbatim quote.
- `app/calculator.py`: pure functions. Metric, status, and position vs benchmark. No I/O, no model.
- `app/agent.py`: the Charity Research Agent (PydanticAI, gpt-6-luna via Portkey). Given a charity name and URL, it fetches the page with a bounded tool, and returns structured inputs with quotes. Code verifies every quote and number against the fetched text, then the calculator does the math.
- `app/main.py`: FastAPI. Serves the API and a no-build static frontend (`web/`).
- Donor view: pick a cause, see a ranked table, source links on every number, and "can't compute" rows.
- Philanthropy view: upload a CSV of funded charities; each row is computed from given numbers or researched by the agent, then placed against the benchmark.
- Guards: token budget per run and per day, request/tool-call caps, fetch size cap, key redaction in logs.
- `eval/`: labelled test pages to measure extraction accuracy; token log to measure cost.

## Build order (no stops between steps)
1. Benchmark table (sourced)  
2. Calculator + tests  
3. Charity agent  
4. Donor view + philanthropy view  
5. Safety tests  
6. Accuracy + token cost measurement  
Then: README, .env.example, screenshots, report.html, slides.html.

## To-do
- [ ] Repo skeleton, git init, .gitignore (.env, .venv), .env.example
- [ ] Research and verify benchmarks for all four causes (source URL, source date, accessed date, quote)
- [ ] Research curated charities per cause, same provenance rules
- [ ] Calculator: metrics, can't-compute reasons, benchmark position, ranking
- [ ] Calculator unit tests
- [ ] .env loader (repo folder, then parent) + Portkey model config
- [ ] Charity agent: fetch tool, structured output, quote/number verification
- [ ] Usage limits + token logging per run
- [ ] FastAPI endpoints: causes, ranking, analyze charity, upload portfolio
- [ ] Frontend: donor view, philanthropy view, source links, token usage display
- [ ] Sample portfolio CSV for the philanthropy view
- [ ] Safety tests: prompt injection pages, fabricated numbers, key redaction, budget caps, .env lookup
- [ ] Eval set + accuracy script; token cost script and results
- [ ] README with fresh-clone steps; dry run with .env one folder up
- [ ] Screenshots; report.html (10–15 pages); slides.html (reveal.js, ≤10 slides)
- [ ] Real user test (Michael to arrange) for Impact evidence
