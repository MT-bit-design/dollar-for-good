# Dollar for Good: a charity impact tool

A donor picks a cause (**health**, **poverty and cash transfers**, **education**, or **climate**) and sees charities ranked by how much good each dollar does, in the right unit for that cause:

| Cause | Unit | Better is |
|---|---|---|
| Health | Cost per DALY averted | lower |
| Poverty and cash transfers | Income gained per dollar | higher |
| Education | Cost per extra year of learning | lower |
| Climate | Cost per tonne CO2e averted | lower |

A funder can also upload the charities they fund (CSV) and see where each one sits against its cause benchmark.

**The rules the app follows**
- Every benchmark and charity number has a source link, a date, and the exact quote it came from. If the number isn't in its own quote, it isn't used. Anything unsourced is marked *missing*, never guessed.
- All math is plain Python (`app/calculator.py`). The AI model only finds and quotes figures.
- A charity that can't be computed is listed with the reason, not ranked.
- Website text is untrusted. Injection attempts are detected in code, and any quote that isn't word-for-word on a page the agent actually fetched is rejected.

## Run it locally (about 5 minutes)

You need **Python 3.11 or newer** and a **`PORTKEY_API_KEY`** (course key, model `gpt-6-luna`). Without a key, the donor view and the portfolio view still work for every charity in the sourced table. Only the research agent is turned off.

1. **Get the code** and open a terminal **inside the project folder** (the one with `run.py` in it). Every command below must be run from there:
   ```
   cd path	o\dollar-for-good
   ```
   If you see `The module '.venv' could not be loaded` or `No such file`, you are in the wrong folder.

2. **Make a virtual environment and install the packages.**

   Windows (PowerShell or Command Prompt):
   ```
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   macOS / Linux:
   ```
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. **Add the key.** The app looks for a `.env` file in **this folder first, then in the folder above it**. So if your `.env` with `PORTKEY_API_KEY=...` already sits one level up (e.g. `submissions/.env`), there is nothing to do. Otherwise:
   ```
   copy .env.example .env        (Windows)
   cp .env.example .env          (macOS / Linux)
   ```
   and put your key after `PORTKEY_API_KEY=`. `.env` is git-ignored. Never commit it.

4. **Start the app.**
   ```
   .\.venv\Scripts\python.exe run.py      (Windows)
   .venv/bin/python run.py                (macOS / Linux)
   ```
   Open **http://127.0.0.1:8000**. The footer shows whether the key was found.

## Using it
- **Compare charities**: pick a cause card. You see the benchmark (with its source and quote), the ranked charities, and a "Can't compute yet" list with reasons. Open "Quote and notes" on any row to see exactly where the number came from.
- **Research a charity that isn't listed**: enter a name and website. The research agent reads the site (and known evaluators), quotes a figure, and code verifies it. You see each step the agent took and the tokens and cost of the run.
- **Check my portfolio**: press **Try the sample portfolio**, or upload your own CSV with columns
  `name, cause, website, amount_granted_usd, cost_usd, outcome_amount` (only `name` is required). Each row uses your own numbers if given, else the sourced table, else the research agent (up to 10 rows per upload). Sample file: `data/sample_portfolio.csv`.

## Tests
```
.venv\Scripts\python.exe -m pytest -q
```
94 offline tests: calculator, sourcing rules, and safety (prompt injection, invented numbers, unsafe URLs, loops, token budget, key leaks, `.env` lookup). They use a scripted fake model, so they need no key and cost nothing.

Live tests against the real model (cost a few cents of tokens):
```
set RUN_LIVE=1 && .venv\Scripts\python.exe -m pytest tests/test_live.py -s      (Windows cmd)
RUN_LIVE=1 .venv/bin/python -m pytest tests/test_live.py -s                       (macOS / Linux)
```

## Accuracy and cost
```
.venv\Scripts\python.exe -m eval.run_eval --name my_run
```
Runs the research agent on 18 labelled cases (14 synthetic pages including traps and injections, plus 4 real charity sites) and records accuracy and token use in `eval/results/`. The current results and the cost model are in [eval/RESULTS.md](eval/RESULTS.md): **0 wrong numbers shown on 18 cases, 89% accuracy, about 4,100 input tokens (74% cached) and 130 output tokens per research run.**

## How it's built
```
app/calculator.py   all impact math (pure functions)
app/data.py         loads the sourced table and enforces the sourcing rules
app/agent.py        Charity Research Agent (PydanticAI + gpt-6-luna via Portkey), code verification, budget, usage log
app/fetch.py        safe page fetching: allow-listed domains, no private IPs, hidden text stripped, injection detection
app/portfolio.py    the funder CSV view
app/main.py         FastAPI API + static site
web/                the website (plain HTML/CSS/JS, no build step)
data/research/      the sourced benchmark and charity table (link, date, quote, notes for every number)
eval/               labelled test pages, eval script, results
tests/              offline and live tests
```

The data set is small (one JSON file per pair of causes), so there is no separate "big data" mode.

## Limits
- The sourced table is small (21 charities, 13 with usable numbers; 9 benchmarks, 7 sourced), and estimates come from different evaluators, years and methods. Climate advocacy figures are highly uncertain expected values.
- A charity's own site can state conflicting figures. The agent verifies that a quote is real, not that the charity's claim is right.
- Dollar costs use the per-token rates in `app/config.py` (`PRICE_PER_M_*`). Check them against the current gpt-6-luna price list.
