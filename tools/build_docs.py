r"""Build report.html and slides.html as single self-contained files.

    .venv\Scripts\python.exe tools/build_docs.py

Reads docs/report_src.html and docs/slides_src.html, replaces {{img:NAME}} with the
screenshot docs/screenshots/NAME.png as an embedded JPEG data URI, and {{file:PATH}}
with the escaped text of a file (used for real test output).
"""

import base64
import html
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"


def data_uri(name: str, max_width: int = 1400) -> str:
    img = Image.open(SHOTS / f"{name}.png").convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


USER_TEST = ROOT / "docs" / "user_test" / "results.json"

PENDING_REPORT = """<div class="todo"><b>To be added before submission.</b> Michael will run the user test in
  <code>docs/user_test/user_test_kit.html</code> with a real donor or program officer: a timed ranking task without the
  tool (5 poverty charities), then with it (5 education charities), plus an interview. Results go in
  <code>docs/user_test/results.json</code> and appear here when the report is rebuilt.
  No user result is claimed in this report until then.</div>"""
PENDING_SLIDE = '<li class="muted">Real user test: to be added (timed, before and after, with a quote).</li>'


def _e(v) -> str:
    return "not measured" if v is None else html.escape(str(v))


def _yn(v) -> str:
    return "not measured" if v is None else ("yes" if v else "no")


def user_test_blocks() -> tuple[str, str]:
    """The report section and slide line for the real user test. Plain code, no guessing:
    anything missing in results.json is shown as 'not measured'."""
    try:
        r = json.loads(USER_TEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PENDING_REPORT, PENDING_SLIDE
    if not r.get("completed"):
        return PENDING_REPORT, PENDING_SLIDE

    rounds = r.get("rounds") or []
    rows = "".join(
        f"<tr><td>{_e(x.get('round'))}: {_e(x.get('set'))}</td><td>{'with the tool' if x.get('with_tool') else 'without'}</td>"
        f"<td class='n'>{_e(x.get('minutes'))}{' min' if x.get('minutes') is not None else ''}"
        f"{' (hit cap)' if x.get('hit_cap') else ''}</td>"
        f"<td>{_e(x.get('top_pick'))} ({_yn(x.get('top_pick_correct'))})</td>"
        f"<td class='n'>{_e(x.get('order_correct'))} / {_e(x.get('order_out_of'))}</td>"
        f"<td>{_yn(x.get('unknowns_flagged'))}</td><td>{_yn(x.get('cited_source_for_top_pick'))}</td>"
        f"<td class='n'>{_e(x.get('confidence_1to5'))}</td></tr>" for x in rounds)
    before = next((x for x in rounds if not x.get("with_tool")), {})
    after = next((x for x in rounds if x.get("with_tool")), {})
    m0, m1 = before.get("minutes"), after.get("minutes")
    speed = ""
    if isinstance(m0, (int, float)) and isinstance(m1, (int, float)) and m1 > 0:
        capped = "at least " if before.get("hit_cap") else ""   # stopped at the cap: true time was longer
        speed = (f"<div class='callout'><b>{capped}{m0:g} minutes without the tool vs. {m1:g} minutes with it "
                 f"({capped}{m0 / m1:.1f}x faster)</b>, measured on one participant. The two rounds used different charity "
                 f"sets and the second round benefits from practice, so treat this as one real data point, "
                 f"not a controlled study.</div>")
    who = f"On {_e(r.get('date'))}, <b>{_e(r.get('participant_role'))}</b>"
    if r.get("participant_context"):
        who += f" ({_e(r.get('participant_context'))})"
    who += " tried the app, following the kit in <code>docs/user_test/user_test_kit.html</code>."
    extra = ""
    for label, key in [("How they do it today", "how_they_do_it_today"),
                       ("Round 3, comparing the app with their own Round 1 answer", "round3_reaction"),
                       ("Would they use it", "would_use"), ("Most confusing part", "most_confusing"),
                       ("Time it would save them", "time_saved_estimate_per_year")]:
        if r.get(key):
            extra += f"<li><b>{label}:</b> {_e(r[key])}</li>"
    own = r.get("own_charities") or {}
    if own.get("tried"):
        extra += (f"<li><b>Their own charities</b> ({_e(', '.join(own.get('names') or []))}): "
                  f"{_e(own.get('outcome'))}</li>")
    quotes = "".join(f"<div class='callout' style='font-style:italic'>“{_e(q)}”"
                     f"<br><span style='font-style:normal;font-size:13px'>— {_e(r.get('participant_role'))}</span></div>"
                     for q in r.get("quotes") or [])
    shot = ""
    if r.get("screenshot"):
        shot = (f"<figure><img src='{{{{img:{html.escape(r['screenshot'])}}}}}' alt='User test'>"
                f"<figcaption>The participant's session.</figcaption></figure>")
    report = (f"<p>{who}</p><table><tr><th>Round</th><th>Tool</th><th class='n'>Time</th><th>#1 pick (correct?)</th>"
              f"<th class='n'>Order right</th><th>Flagged unknowns</th><th>Cited a source</th><th class='n'>Confidence 1–5</th></tr>"
              f"{rows}</table>{speed}{'<ul>' + extra + '</ul>' if extra else ''}{quotes}{shot}")

    bits = [f"Real user ({_e(r.get('participant_role'))})"]
    if isinstance(m0, (int, float)) and isinstance(m1, (int, float)):
        bits.append(f"{'≥' if before.get('hit_cap') else ''}{m0:g} min → {m1:g} min")
    c0, c1 = before.get("confidence_1to5"), after.get("confidence_1to5")
    if c0 is not None and c1 is not None:
        bits.append(f"confidence {c0} → {c1} of 5")
    slide = "<li><b>" + ": ".join([bits[0], " · ".join(bits[1:])]) + "</b>" if len(bits) > 1 else "<li><b>" + bits[0] + "</b>"
    if r.get("quotes"):
        slide += f" <i>“{_e(r['quotes'][0])}”</i>"
    return report, slide + "</li>"


def build(src: str, out: str) -> None:
    text = (ROOT / "docs" / src).read_text(encoding="utf-8")
    report_block, slide_block = user_test_blocks()
    text = text.replace("{{user_test_report}}", report_block).replace("{{user_test_slide}}", slide_block)
    if "{{diagram}}" in text:   # the agent diagram is drawn once, in the report source
        src_report = (ROOT / "docs" / "report_src.html").read_text(encoding="utf-8")
        svg = src_report[src_report.index('<svg class="diagram"'): src_report.index("</svg>") + 6]
        text = text.replace("{{diagram}}", svg)
    text = re.sub(r"\{\{img:([\w-]+)\}\}", lambda m: data_uri(m.group(1)), text)
    text = re.sub(r"\{\{file:([\w./-]+)\}\}",
                  lambda m: html.escape((ROOT / m.group(1)).read_text(encoding="utf-8")), text)
    (ROOT / out).write_text(text, encoding="utf-8")
    print(f"{out}: {len(text) / 1e6:.1f} MB")


if __name__ == "__main__":
    build("report_src.html", "report.html")
    if (ROOT / "docs" / "slides_src.html").exists():
        build("slides_src.html", "slides.html")
