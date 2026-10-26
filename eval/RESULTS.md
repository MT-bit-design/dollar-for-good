# Measured accuracy and token cost

All numbers below come from real `gpt-6-luna` runs through Portkey, made with `eval/run_eval.py`
on 2026-10-26. Raw per-case output is in `eval/results/*.json`. Token counts are measured.
Dollar costs = tokens x the rates in `app/config.py`
(input $1.25/1M, cached input $0.125/1M, output $10.0/1M).
**These rates are placeholders and must be checked against the course's gpt-6-luna price list**;
change them in `app/config.py` (or the `PRICE_PER_M_*` env vars) and every cost here and in the app updates.

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
| 1. First version | 78% | 2 | 64% | 100% | 3,401 | 662 | 154 | $0.0050 | 5.5s |
| 2. Parser + percent fixes | 78% | 1 | 64% | 100% | 3,507 | 695 | 125 | $0.0049 | 6.6s |
| 3. Code check as validator, one retry (**shipped**) | 89% | 0 | 82% | 100% | 4,116 | 3,059 | 132 | $0.0030 | 5.8s |
| Experiment: page text cut to 4,000 chars | 89% | 0 | 82% | 100% | 3,179 | 2,395 | 124 | $0.0025 | 2.1s |
| Experiment: reasoning effort medium | 89% | 0 | 82% | 100% | 5,348 | 3,728 | 297 | $0.0055 | 7.4s |

What changed between versions, and why:
1. **First version**: 2 wrong numbers. GiveDirectly's "2.5x" was parsed as 2 (a parser bug), and
   Village Enterprise returned a different figure than our table. It also missed two valid figures
   ("210%" and "1.25 million tonnes of CO2", where the "2" in CO2 broke the parser).
2. **Parser fixes**: numbers glued to letters (CO2) are ignored, "2.5x" parses, percent ratios are supported.
   This exposed a new wrong number: GiveDirectly's "83% of expenses delivered to recipients" read as income per dollar.
3. **Shipped**: the poverty check now requires the quote to talk about income/benefit *and* per-dollar form,
   the prompt explains how to fill "X per $Y", and the code check runs as an output validator so the
   model gets one retry with the exact reason. Result: **0 wrong numbers, 100% precision, 89% accuracy**.

Remaining misses (honest):
- GiveDirectly (real site): the agent refused; the site's "2.5x local economic activity" is a valid figure
  that our checks now treat cautiously. A miss, not a wrong number.
- Village Enterprise (real site): the homepage says "$5.34 in benefits for every $1 invested", while the
  charity's own blog reports a 140% three-year benefit-cost ratio (our table). The quote is real and verified,
  so we count it as a *verified alternative*, not an error. It shows a real limit: charities publish
  conflicting self-reported figures.

## Did cost cutting hurt quality?
- **Reasoning effort low vs medium**: medium cost 1.8x as much per run and was slower, with identical accuracy.
  We ship low.
- **Page text 12,000 vs 4,000 characters**: 4,000 was 17% cheaper with identical accuracy on this set.
  But the synthetic pages are short, so only the 4 real sites tested this; long real pages can hide the figure
  past 4,000 characters. We keep 12,000 as the safer default. This is a judgement call, not proven either way.
- **Prompt caching**: the system prompt is long and fixed and comes first, so the provider caches it.
  In the shipped version 74% of input tokens were cached.
- **Answer cache**: a charity researched once is stored in `output/agent_cache.json`; repeat lookups cost 0 tokens.
- **Sourced table first**: the donor view and any charity already in the table use no model at all.

## Tokenomics (shipped version)
- One research run: 4,116 input tokens (3,059 cached), 132 output tokens,
  2.3 model calls, about 6 s. **$0.0030 per run** at the configured rates.
- Browsing the donor view: 0 tokens.
- Assumed monthly use (an estimate, not measured): a donor researches 4 new charities a month;
  a foundation program officer uploads one portfolio with 10 un-listed charities plus 4 one-off lookups.

| | Runs/month | Cost/month |
|---|---|---|
| One donor | 4 | $0.012 |
| One foundation user | 14 | $0.042 |
| 100 foundation users | 1,400 | $4.23 |
| 10,000 foundation users | 140,000 | $422.93 |

These are upper bounds: the shared answer cache means a charity researched for one user is free for the next,
so at 10,000 users most popular charities would already be cached.

## Guards measured in tests
- Per run: at most 6 model calls, 4 page fetches, 60,000 tokens.
- Per day: 1,000,000 tokens across all users; when reached, research is refused before any model call.
- Per upload: 25 rows, 10 researched by the agent.
