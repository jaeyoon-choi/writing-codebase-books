#!/usr/bin/env python3
"""Set TrimBox and BleedBox on every page of a PDF that Chrome printed with bleed.

Chrome writes MediaBox only, so a printer's preflight cannot tell where the
trim is. This appends an incremental update (new versions of the page
objects plus a new xref section) and leaves the original bytes as they are.
It handles the classic xref table that Chrome's Skia backend writes, not
xref streams.

Usage: python3 -I tools/pdf_boxes.py BOOK.pdf --bleed-mm 3
"""

import argparse
import re
from pathlib import Path

MM = 72 / 25.4


def read_xref(data):
    start = int(re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", data).group(1))
    if not data.startswith(b"xref", start):
        raise SystemExit("not a classic xref table (xref streams are not supported)")
    offsets = {}
    pos = start + 4
    while True:
        m = re.compile(rb"\s*(\d+) (\d+)\s*\n").match(data, pos)
        if not m:
            break
        first, count = int(m.group(1)), int(m.group(2))
        pos = m.end()
        for i in range(count):
            entry = data[pos:pos + 20]
            if entry[17:18] == b"n":
                offsets[first + i] = int(entry[:10])
            pos += 20
    trailer = re.compile(rb"\s*trailer\s*(<<.*?>>)\s*startxref", re.S).match(data, pos).group(1)
    return start, offsets, trailer


def set_boxes(path, bleed_mm):
    data = Path(path).read_bytes()
    start, offsets, trailer = read_xref(data)
    b = bleed_mm * MM
    updates = []
    for num, off in sorted(offsets.items()):
        m = re.compile(rb"(\d+) 0 obj\s*").match(data, off)
        body = data[m.end():data.index(b"endobj", m.end())]
        if not re.search(rb"/Type\s*/Page\b(?!s)", body) or b"/TrimBox" in body:
            continue
        x0, y0, x1, y1 = (float(v) for v in re.search(rb"/MediaBox\s*\[([^\]]*)\]", body).group(1).split())
        boxes = (f"/BleedBox [{x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f}] "
                 f"/TrimBox [{x0 + b:.3f} {y0 + b:.3f} {x1 - b:.3f} {y1 - b:.3f}] ").encode()
        i = body.index(b"<<") + 2
        updates.append((num, body[:i] + boxes + body[i:].rstrip() + b"\n"))
    if not updates:
        return 0
    out = bytearray(data if data.endswith(b"\n") else data + b"\n")
    new_offsets = []
    for num, body in updates:
        new_offsets.append((num, len(out)))
        out += f"{num} 0 obj\n".encode() + body + b"endobj\n"
    xref = len(out)
    out += b"xref\n"
    for num, off in new_offsets:
        out += f"{num} 1\n{off:010d} 00000 n \n".encode()
    size = re.search(rb"/Size\s+(\d+)", trailer).group(1)
    keep = b" ".join(re.findall(rb"/(?:Root|Info)\s+\d+ \d+ R", trailer))
    out += b"trailer\n<</Size " + size + b" " + keep + f" /Prev {start}>>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(bytes(out))
    return len(updates)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--bleed-mm", type=float, default=3.0)
    a = ap.parse_args()
    print(f"{a.pdf}: boxes set on {set_boxes(a.pdf, a.bleed_mm)} pages")
