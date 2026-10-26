#!/usr/bin/env python3
"""Make TrueType copies of the CJK fonts for the book build.

Chrome's PDF backend embeds fonts with CFF outlines as Type 3 fonts, which
print shops reject, and embeds fonts with TrueType outlines as CID TrueType.
The Noto CJK fonts ship only with CFF outlines, so this module subsets each
face to the characters of the book and converts its outlines to quadratic
TrueType curves. build_pdf.py loads the results with @font-face under the
original family names, so book.css needs no change.
"""

import hashlib
import subprocess
from pathlib import Path

from fontTools import subset
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

# (CSS family, CSS weight, fontconfig pattern)
FACES = [
    ("Noto Serif CJK KR", 400, "Noto Serif CJK KR:style=Regular"),
    ("Noto Serif CJK KR", 600, "Noto Serif CJK KR:style=SemiBold"),
    ("Noto Serif CJK KR", 700, "Noto Serif CJK KR:style=Bold"),
    ("Noto Sans CJK KR", 400, "Noto Sans CJK KR:style=Regular"),
    ("Noto Sans CJK KR", 700, "Noto Sans CJK KR:style=Bold"),
    ("Noto Sans Mono CJK KR", 400, "Noto Sans Mono CJK KR:style=Regular"),
]
# Always kept, so small text edits do not need new glyphs.
BASE_CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "·…‘’“”–→←↑↓×÷≤≥≈±°µ①②③④⑤⑥⑦⑧⑨"


def _locate(pattern):
    out = subprocess.run(["fc-match", "-f", "%{file}:%{index}", pattern], capture_output=True, text=True,
                         check=True).stdout
    path, index = out.rsplit(":", 1)
    return path, int(index)


def _to_truetype(font):
    """Replace the CFF table with glyf and loca (after fontTools' otf2ttf snippet)."""
    order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyphs[name] = pen.glyph()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = glyphs
    for tag in ("CFF ", "VORG"):
        if tag in font:
            del font[tag]
    glyf.compile(font)
    hmtx = font["hmtx"]
    for name, g in glyf.glyphs.items():
        if hasattr(g, "xMin"):
            hmtx[name] = (hmtx[name][0], g.xMin)
    font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    for attr in ("maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                 "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, attr, 0)
    maxp.compile(font)
    font["post"].formatType = 3.0       # no glyph names: CID fonts have none worth keeping
    font.sfntVersion = "\000\001\000\000"


def make_fonts(text, out_dir):
    """Write one TrueType file per face to out_dir and return the @font-face CSS for them."""
    chars = "".join(sorted(set(text) | set(BASE_CHARS)))
    key = hashlib.sha1(chars.encode()).hexdigest()[:12]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    css = []
    for family, weight, pattern in FACES:
        path, index = _locate(pattern)
        dest = out_dir / f"{Path(path).stem}-{index}-{key}.ttf"
        if not dest.exists():
            for old in out_dir.glob(f"{Path(path).stem}-{index}-*.ttf"):
                old.unlink()
            font = TTFont(path, fontNumber=index, lazy=False)
            opts = subset.Options()
            opts.layout_features = ["*"]
            opts.name_IDs = ["*"]
            opts.notdef_outline = True
            opts.glyph_names = False
            sub = subset.Subsetter(opts)
            sub.populate(text=chars)
            sub.subset(font)
            _to_truetype(font)
            font.save(dest)
        css.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
                   f'src: url("fonts/{dest.name}") format("truetype"); }}')
    return "\n".join(css)


if __name__ == "__main__":
    import sys
    print(make_fonts(sys.stdin.read(), sys.argv[1] if len(sys.argv) > 1 else "build/fonts"))
