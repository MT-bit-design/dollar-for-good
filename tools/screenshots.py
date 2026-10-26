"""Take the app screenshots used in the report and slides.

Start the app first (python run.py), then:
    .venv\\Scripts\\python.exe -m pip install playwright
    .venv\\Scripts\\python.exe tools/screenshots.py
Uses the installed Microsoft Edge, so no browser download is needed.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
only = set(sys.argv[1:])


def abs_box(page, selector, last=False):
    """Element box in page coordinates (independent of scrolling), for full-page clips."""
    return page.evaluate("""([sel, last]) => {
        const els = document.querySelectorAll(sel); const el = last ? els[els.length - 1] : els[0];
        const r = el.getBoundingClientRect();
        return {x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height};
    }""", [selector, last])


def want(name):
    return not only or name in only


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=1.5)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(BASE)
        page.wait_for_selector("#groups table tbody tr")

        for cause in ["health", "poverty", "education", "climate"]:
            if want(f"donor_{cause}"):
                page.click(f'.cause-card[data-cause="{cause}"]')
                page.wait_for_timeout(400)
                page.screenshot(path=OUT / f"donor_{cause}.png", full_page=True)

        if want("donor_quote"):
            page.click('.cause-card[data-cause="poverty"]')
            page.wait_for_timeout(400)
            page.locator("#groups details").first.locator("summary").click()
            page.locator(".table-wrap").first.screenshot(path=OUT / "donor_quote.png")

        if want("crops"):
            # Tight crops for slides: benchmark + ranking (poverty), portfolio tiles + first rows.
            page.click('.cause-card[data-cause="poverty"]')
            page.wait_for_timeout(400)
            top = abs_box(page, ".bench")
            bot = abs_box(page, "#groups .table-wrap", last=True)
            page.screenshot(path=OUT / "crop_donor.png", full_page=True,
                            clip={"x": top["x"] - 10, "y": top["y"] - 10, "width": top["width"] + 20,
                                  "height": bot["y"] + bot["height"] - top["y"] + 20})

        if want("research"):
            page.click('.cause-card[data-cause="poverty"]')
            page.fill('#research-form [name=name]', "One Acre Fund")
            page.fill('#research-form [name=website]', "https://oneacrefund.org")
            page.select_option('#research-form [name=cause]', "poverty")
            page.click('#research-form button')
            page.wait_for_selector("#research-out .result .headline, #research-out .alert", timeout=120_000)
            page.locator("#research-out details summary").first.click()
            page.wait_for_timeout(200)
            page.locator("#research-card").screenshot(path=OUT / "research_run.png")

        if want("portfolio"):
            page.click('.tab[data-tab="funder"]')
            page.click("#sample-go")
            page.wait_for_selector("#portfolio-out .tiles", timeout=180_000)
            page.wait_for_timeout(300)
            page.screenshot(path=OUT / "portfolio.png", full_page=True)
            t = abs_box(page, "#portfolio-out .tiles")
            r5 = page.evaluate("""() => { const r = document.querySelectorAll('#portfolio-out tbody tr')[4].getBoundingClientRect();
                                  return {y: r.top + window.scrollY, height: r.height}; }""")
            page.screenshot(path=OUT / "crop_portfolio.png", full_page=True,
                            clip={"x": t["x"] - 10, "y": t["y"] - 10, "width": t["width"] + 20,
                                  "height": r5["y"] + r5["height"] - t["y"] + 20})

        if want("aisafety"):
            page.click('.tab[data-tab="aisafety"]')
            page.wait_for_selector("#ais-list li")
            page.screenshot(path=OUT / "aisafety.png", full_page=True)

        if want("method"):
            page.click('.tab[data-tab="method"]')
            page.screenshot(path=OUT / "method.png", full_page=True)

        browser.close()
        print("console errors:", errors or "none")
        print("saved to", OUT)


if __name__ == "__main__":
    main()
