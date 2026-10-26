r"""Build report.html and slides.html as single self-contained files.

    .venv\Scripts\python.exe tools/build_docs.py

Reads docs/report_src.html and docs/slides_src.html, replaces {{img:NAME}} with the
screenshot docs/screenshots/NAME.png as an embedded JPEG data URI, and {{file:PATH}}
with the escaped text of a file (used for real test output).
"""

import base64
import html
import io
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


def build(src: str, out: str) -> None:
    text = (ROOT / "docs" / src).read_text(encoding="utf-8")
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
