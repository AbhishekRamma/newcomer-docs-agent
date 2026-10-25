"""Measure the rendered contrast of white text on the chat page's orange controls.

For each element, hide its text, take a screenshot of the text's bounding box, find the
lightest background pixel and compute the WCAG contrast ratio against #ffffff.

Usage: uv run --with playwright --with pillow python scripts/check_contrast.py http://localhost:8010/
"""

import io
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

SELECTORS = (".gel", ".msg.user .bubble")
VIEWPORTS = ((1280, 900), (390, 844))
ADD_USER_BUBBLE = """() => {
  const u = document.createElement('article');
  u.className = 'msg user';
  const p = document.createElement('p');
  p.className = 'bubble';
  p.textContent = 'How long can I drive here?';
  u.append(p);
  document.getElementById('log').append(u);
}"""


def luminance(rgb: tuple[int, int, int]) -> float:
    c = [v / 255 for v in rgb]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def text_box(page, sel: str) -> list[float]:
    return page.evaluate(
        """(sel) => { const r = document.createRange();
          r.selectNodeContents(document.querySelector(sel));
          const b = r.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }""",
        sel,
    )


def main(base: str) -> int:
    worst = 99.0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        for w, h in VIEWPORTS:
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            page.goto(base)
            page.wait_for_timeout(800)
            page.evaluate(ADD_USER_BUBBLE)
            page.add_style_tag(content=".crt{display:none!important} *{animation:none!important}")
            for sel in SELECTORS:
                x, y, bw, bh = text_box(page, sel)
                page.add_style_tag(
                    content=f"{sel}{{color:transparent!important;text-shadow:none!important}}"
                )
                png = page.screenshot(clip={"x": x, "y": y, "width": bw, "height": bh})
                im = Image.open(io.BytesIO(png)).convert("RGB")
                lightest = max(
                    im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata(),
                    key=luminance,
                )
                ratio = 1.05 / (luminance(lightest) + 0.05)
                worst = min(worst, ratio)
                hexcol = "".join(f"{v:02x}" for v in lightest)
                print(f"{w}px {sel:22s} lightest bg #{hexcol}  contrast vs white = {ratio:.2f}:1")
            page.close()
        browser.close()
    print(f"worst {worst:.2f}:1 -> {'PASS' if worst >= 4.5 else 'FAIL'} (WCAG AA 4.5:1)")
    return 0 if worst >= 4.5 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"))
