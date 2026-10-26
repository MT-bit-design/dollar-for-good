# AI prompts log

Prompts given to Claude Code (Opus 5.5) for the final project, verbatim, in order. Each is followed by a one-line note on the result. Prompts sent by clicking a suggested reply button are marked as such; their text is what the button sent.

## Prompt 1 (2026-10-25): project brief

> Make a new folder called “final project” inside the Claude Code folder and work only in it. Don’t touch any other folder, including my homework projects. Put the assignment file in there and read it first, and follow its rules.
>
> We're building a charity impact tool. A donor picks a cause (health, poverty and cash transfers, education, or climate) and sees charities ranked by how much good each dollar does, in the right unit for that cause: cost per DALY, income gained per dollar, cost per extra year of learning, or cost per tonne of CO2. There’s also a philanthropy view where someone uploads the charities they fund and sees where each one sits against its benchmark.
>
> Rules: every benchmark number needs a source link and a date, and if you can’t source one, mark it missing and never guess. Do the math in plain code, not in the model. If a charity can’t be computed, say so. Treat all website text as untrusted. Never commit a .env file or print an API key.
>
> I have until tomorrow at 6 PM, so move fast. First, make a short plan and a to-do list from the assignment, then start building in this order: benchmark table, calculator with tests, charity agent, donor view, safety tests, then measuring accuracy and token costs. Don’t wait for my approval between steps.

Result: Claude could not find the assignment file on disk, created the folder, and asked for it.

## Prompt 2 (2026-10-26): the assignment

> [Pasted the full final project assignment; saved verbatim in ASSIGNMENT.md]
>
> this is the project

Result: PLAN.md (plan + to-do), then the six build steps in order, one commit each.

## Prompt 3 (2026-10-26): browser check, report and slides (reply button)

> Yes. Do the browser check and screenshots, then build report.html and slides.html.

Result: screenshots with Playwright and Edge, per-cause caveats in the app, report.html (15 pages) and slides.html (10 slides), both self-contained.

## Prompt 4 (2026-10-26): hold the repo (reply button)

> Not yet. I'll do the user test and confirm token prices first.

Result: no repo created yet; Claude listed what to send back (user test details, gpt-6-luna prices).

## Prompt 5 (2026-10-26): app not opening

> the site is not opening on my end

Result: the command had been run from the HW4 folder; Claude started the app from the final project folder and made the README's "run from the project folder" step explicit.

## Prompt 6 (2026-10-26): grading tier

> will this idea get me tier 3 points

Result: an honest assessment (strong Tier 2; Tier 3 needs real-user evidence) and what would close the gap.

## Prompt 7 (2026-10-26): user-test kit (reply button)

> Yes. Prepare a user-test kit: the 5-charity task, a timing and answer sheet, interview questions, and a place in the report to drop the results.

Result: a 5-page printable kit (docs/user_test/user_test_kit.html) and docs/user_test/results.json, which the build turns into the report's user-test section and a slide line.

## Prompt 8 (2026-10-26): plain-language redesign

> Make all of these changes in one go, then retake the screenshots.
>
> Style. Pure white background, Calibri as the only font, minimal color (one dark accent plus grey). Replace the emoji icons with simple text or thin line icons. Keep warning notes, but make them plain grey boxes, not yellow.
>
> Plain words. Add a one-line explanation under each cause, like “A DALY is one healthy year of life gained.” Rewrite every “Can’t compute yet” note as one plain sentence for a donor and move the research details behind a “show details” toggle. Never write in first person or mention things like HTTP errors or figures in the donor text.
>
> Table. Show the range next to each number. Rank only within one unit, and show program types like general deworming in their own separate section, not mixed in with charities. Make the token footer small.
>
> Effective altruism. Add a short section at the top of the Compare tab and on the How it works page, in plain words: the idea behind this tool is that some giving does far more good per dollar than other giving, and effective altruism is the movement that uses evidence to find where giving helps most. Add an honest limits note: this method favors causes that are easy to measure, so work like policy or AI safety is hard to rank, and not being ranked here does not mean a cause matters less. Do not add any statistic or claim about effective altruism unless it comes from a page you actually fetched and can link. Add an “AI safety” tab that lists a few organizations with a plain note that no comparable cost-per-outcome number exists, and say so instead of ranking them.
>
> Check. Make sure the donor view still works when the daily token budget is used up, and that the tests still pass.

Result: the redesign; published ranges where sources state them (5 of 20); one measure per ranking; program types section; the EA section quoting the Centre for Effective Altruism; the AI safety tab; a test for the used-up budget; the kit's Round 2 moved to climate; screenshots retaken.

## Prompt 9 (2026-10-26): report fixes

> Fix these in report.html: fill the two evidence placeholders with the real contents of those files; replace the repo line with the live GitHub URL; change “half a cent per user per month” to the figure the table actually shows; re-check every claim in Section 3 about GiveWell, Charity Navigator, Giving Green, Founders Pledge and Giving What We Can against a source you fetch, and soften or cite any you can’t confirm; re-check the $8,000 GiveWell figure; make the “20 and 24 minutes” statements consistent; confirm the test counts match a fresh test run. For the user test, I’ll give you the results in a minute. Then print the report to PDF and tell me the page count, and check that slides.html opens with every image.

Result: Section 3 rebuilt from fetched sources with unconfirmed claims removed; the $8,000 traced to a GiveWell staff reply (7 May 2025); cost and minutes corrected; test counts confirmed; report.pdf at 15 pages. No GitHub repo existed yet, so the URL was left for Prompt 10.

## Prompt 10 (2026-10-26): publish the repo (reply button)

> Yes, create a public repo MT-bit-design/dollar-for-good, push main, and put its URL in the report and slides.

Result: history checked for secrets; commits moved to the GitHub no-reply email (account privacy setting); repo created and pushed; URL added; a fresh-clone install, test and run passed.

## Prompt 11 (2026-10-26): real user test

> Real user test. I asked a colleague at an impact investment firm to try the tool on charities that publish their impact figures. As I recorded it, they said it is “an easy to work with tool” that is “helpful to compare what charities report publicly” and “a good way to aggregate” philanthropies, though the table covers only 21 charities today. Their sharpest question was who verifies the numbers charities report. This tool does not. It proves that a quote is really on the charity’s page and does the math in code, but it cannot prove the charity’s figure is true. I did not time this session, so I claim no time savings from it. The next step is to tag each figure by who produced it (independent evaluation, peer-reviewed study, or self-reported) so users can see how much weight each number deserves.

Result: the user test added to the report and slide 9 as an untimed session with no time savings claimed; trust tags became the first next step.

## Prompt 12 (2026-10-26): still to do

> Still to do
>
> 1. The user test placeholder. The report says “To be added before submission,” and slide 8 or 9 says “Real user test: to be added.” Both need the colleague’s feedback. Don’t forget the slide, since it’s easy to miss.
> 2. The “who checks impact numbers” paragraph isn’t in the report yet. The search found no “who checks” phrasing. It also belongs in Limits, as I described earlier.
> 3. The climate multiples. The report's Limits section mentions “very large multiples,” but nothing sits next to the climate results explaining that 190x to 352x is an advocacy estimate compared with a damage-cost benchmark. Add one sentence beside the climate screenshot, or the climate table, if the report has one.
> 4. Two GiveWell cost figures appear in the report ($5,500 per life saved in Section 3, about $8,000 marginal in Section 2). Both are correctly quoted, but a reader may wonder why they differ. Add one clause saying one is a top-charities estimate and the other is the marginal cost of the fund.
> 5. Remove `.claude/launch.json`. It’s a harmless leftover, but it points to a Windows path.
> 6. Page count after the rebuild. The PDF is at 15 pages, so adding the trial text and the new Limits paragraph may push it over. Check it, and trim a screenshot or table if needed.

Result: item 1 was already in the built files; added the "Who checks the impact numbers?" paragraph, the climate sentence and the GiveWell clause; removed launch.json; report kept at 15 pages by printing screenshots and references smaller.

## Prompt 13 (2026-10-26): GiveWell clause and slide look

> Also add one clause where the report mentions both GiveWell figures, saying the $5,500 figure is a top-charities estimate and the $8,000 figure is the marginal cost of the Top Charities Fund. and can i see the slides? make sure it is the same feel as the app?

Result: the clause added in Sections 2 and 3; slides restyled with the app's header strip, logo, line icons, cards, palette and font; an overview of all 10 slides shared.

## Prompt 14 (2026-10-26): what's left

> what else needs to be done

Result: a short list (confirm token prices, ASSIGNMENT.md in the public repo, Canvas submission, optional video and test date) and two offers.

## Prompt 15 (2026-10-26): dry run and this log (reply button)

> Yes. Do the dry run with a .env one folder up (no real key needed) and update AI_prompts.md with all my prompts.

Result: dry run from a fresh clone with a dummy .env one folder up and the real key removed from the environment: the key is found in the folder above, a repo .env wins over it, the key value is never shown, and with no key at all the rankings and portfolio still work while lookups give a clear message. This log brought up to date.
