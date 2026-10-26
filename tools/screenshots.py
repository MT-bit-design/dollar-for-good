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
        page.wait_for_selector("#rank-table tbody tr")

        for cause in ["health", "poverty", "education", "climate"]:
            if want(f"donor_{cause}"):
                page.click(f'.cause-card[data-cause="{cause}"]')
                page.wait_for_timeout(400)
                page.screenshot(path=OUT / f"donor_{cause}.png", full_page=True)

        if want("donor_quote"):
            page.click('.cause-card[data-cause="poverty"]')
            page.wait_for_timeout(400)
            page.locator("#rank-table details").first.locator("summary").click()
            page.locator(".table-wrap").first.screenshot(path=OUT / "donor_quote.png")

        if want("crops"):
            # Tight crops for slides: benchmark + ranking (poverty), portfolio tiles + first rows.
            page.click('.cause-card[data-cause="poverty"]')
            page.wait_for_timeout(400)
            top = page.locator(".bench").bounding_box()
            bot = page.locator(".table-wrap").first.bounding_box()
            page.screenshot(path=OUT / "crop_donor.png", full_page=True,
                            clip={"x": top["x"] - 10, "y": top["y"] - 10, "width": top["width"] + 20,
                                  "height": bot["y"] + bot["height"] - top["y"] + 20})

        if want("research"):
            page.click('.cause-card[data-cause="poverty"]')
            page.fill('#research-form [name=name]', "One Acre Fund")
            page.fill('#research-form [name=website]', "https://oneacrefund.org")
            page.select_option('#research-form [name=cause]', "poverty")
            page.click('#research-form button')
            page.wait_for_selector("#research-out .result h4, #research-out .alert", timeout=120_000)
            page.locator("#research-card").screenshot(path=OUT / "research_run.png")

        if want("portfolio"):
            page.click('.tab[data-tab="funder"]')
            page.click("#sample-go")
            page.wait_for_selector("#portfolio-out .tiles", timeout=180_000)
            page.wait_for_timeout(300)
            page.screenshot(path=OUT / "portfolio.png", full_page=True)
            t = page.locator("#portfolio-out .tiles").bounding_box()
            r5 = page.locator("#portfolio-out tbody tr").nth(4).bounding_box()
            page.screenshot(path=OUT / "crop_portfolio.png", full_page=True,
                            clip={"x": t["x"] - 10, "y": t["y"] - 10, "width": t["width"] + 20,
                                  "height": r5["y"] + r5["height"] - t["y"] + 20})

        if want("method"):
            page.click('.tab[data-tab="method"]')
            page.screenshot(path=OUT / "method.png", full_page=True)

        browser.close()
        print("console errors:", errors or "none")
        print("saved to", OUT)


if __name__ == "__main__":
    main()
