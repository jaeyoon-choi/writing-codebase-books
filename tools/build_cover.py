#!/usr/bin/env python3
"""Print the front cover for the printer: 183 x 235 mm trim with 3 mm bleed.

The cover SVG (cover-print.svg, from figures/src/cover.py) goes inline into
a page of 189 x 241 mm, so its text uses the TrueType fonts from
make_fonts.py and the PDF has no Type 3 fonts. TrimBox and BleedBox are set
with pdf_boxes.py. The spine and back cover are not made: their width
depends on the page count and the paper the printer uses.

Usage: python3 -I tools/build_cover.py [--out build/cover-print.pdf]
"""

import argparse
import html
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pdf import BOOK, BUILD, Chrome  # noqa: E402
from make_fonts import make_fonts  # noqa: E402
from pdf_boxes import set_boxes  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BUILD / "cover-print.pdf"))
    args = ap.parse_args()
    BUILD.mkdir(exist_ok=True)
    svg = (BOOK / "cover-print.svg").read_text(encoding="utf-8")
    svg = re.sub(r'(<svg[^>]*?) width="\d+" height="\d+"', r'\1 width="189mm" height="241mm"', svg, count=1)
    text = html.unescape(" ".join(re.findall(r">([^<]+)<", svg)))
    fonts = make_fonts(text, BUILD / "fonts")
    page = BUILD / "cover-print.html"
    page.write_text('<!doctype html><html><head><meta charset="utf-8"><style>' + fonts +
                    "@page { size: 189mm 241mm; margin: 0; } body { margin: 0; } svg { display: block; }"
                    f"</style></head><body>{svg}</body></html>", encoding="utf-8")
    chrome = Chrome(BUILD / "chrome-profile")
    try:
        chrome.call("Page.enable")
        chrome.call("Page.navigate", url=page.resolve().as_uri())
        while chrome.eval("document.readyState") != "complete" or not chrome.eval(
                "document.fonts.status === 'loaded'"):
            time.sleep(0.2)
        chrome.pdf(args.out)
    finally:
        chrome.close()
    set_boxes(args.out, 3.0)
    print(args.out)


if __name__ == "__main__":
    main()
