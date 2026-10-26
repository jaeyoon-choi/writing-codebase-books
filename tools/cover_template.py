#!/usr/bin/env python3
"""Front cover from book.toml: 183 x 235 mm at 10 px per mm.

Writes cover.svg (trim size, inlined in the screen PDF) and cover-print.svg
(3 mm bleed on every side, for tools/build_cover.py) in the book directory.
The layout is typographic: a colored strip at the top, the subtitle, a
title band and the author. An optional figures/cover-art.svg is placed in
the empty upper area (draw it to fit about 1500 x 1100 px).

Usage: python3 -I tools/cover_template.py [--color #1D5677]
"""

import argparse
import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconf  # noqa: E402

W, H, BLEED = 1830, 2350, 30
SERIF = "'Noto Serif CJK KR', 'Noto Serif', serif"
SANS = "'Noto Sans CJK KR', 'Noto Sans', sans-serif"
BAND_Y, BAND_H = 1520, 330


def svg(b, color, art):
    bk = bookconf.book()
    e = html.escape
    title = bk["title"]
    size = 210 if len(title) <= 8 else max(110, int(210 * 8 / len(title)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * b}" height="{H + 2 * b}" '
        f'viewBox="{-b} {-b} {W + 2 * b} {H + 2 * b}">',
        f'<rect x="{-b}" y="{-b}" width="{W + 2 * b}" height="{H + 2 * b}" fill="#FFFFFF"/>',
        f'<rect x="{-b}" y="{-b}" width="{W + 2 * b}" height="{26 + b}" fill="{color}"/>',
    ]
    if art:
        data = base64.b64encode(art.read_bytes()).decode()
        parts.append(f'<image x="165" y="250" width="1500" height="1100" preserveAspectRatio="xMidYMid meet" '
                     f'href="data:image/svg+xml;base64,{data}"/>')
    parts += [
        f'<text x="120" y="1470" font-family="{SERIF}" font-size="64" fill="{color}">{e(bk.get("subtitle", ""))}</text>',
        f'<rect x="{-b}" y="{BAND_Y}" width="{W + 2 * b}" height="{BAND_H}" fill="{color}"/>',
        f'<text x="120" y="{BAND_Y + 225}" font-family="{SERIF}" font-size="{size}" font-weight="700" '
        f'fill="#FFFFFF">{e(title)}</text>',
        f'<text x="{W - 120}" y="{BAND_Y + BAND_H + 125}" font-family="{SERIF}" font-size="58" font-weight="600" '
        f'fill="#1B1B1B" text-anchor="end">{e(bk["author"])} <tspan font-size="40" font-weight="400" '
        f'fill="#555555">지음</tspan></text>',
        f'<text x="{W - 120}" y="{BAND_Y + BAND_H + 200}" font-family="{SANS}" font-size="32" fill="#666666" '
        f'text-anchor="end">{e(" · ".join(bk.get("title_meta", [])))}</text>',
        "</svg>\n",
    ]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", default="#1D5677")
    args = ap.parse_args()
    art = bookconf.BOOK / "figures" / "cover-art.svg"
    art = art if art.exists() else None
    (bookconf.BOOK / "cover.svg").write_text(svg(0, args.color, art), encoding="utf-8")
    (bookconf.BOOK / "cover-print.svg").write_text(svg(BLEED, args.color, art), encoding="utf-8")
    print(bookconf.BOOK / "cover.svg", bookconf.BOOK / "cover-print.svg")


if __name__ == "__main__":
    main()
