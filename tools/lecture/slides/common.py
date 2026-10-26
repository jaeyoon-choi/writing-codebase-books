"""Building blocks for lecture slides (styles in ../lecture.css).

A lecture module defines NAME (file name), TITLE (shown on the title slide),
KICKER (small label above every slide title) and SLIDES, a list of
dict(title=..., html=..., steps=[...]). An element with data-s="N" appears
from step N of its slide on, and steps[N - 1] is the narration spoken while
step N is on screen. Coordinates are pixels of a 1920 x 1080 frame; the
slide title occupies the band above y = 200.
"""

import html as _html
from pathlib import Path

NAVY = "#1D5677"
AMBER = "#D9A441"
CORAL = "#C8553D"
GREEN = "#5C8A72"
GRAY = "#8A97A3"

import tomllib

_BOOKDIR = Path(__file__).resolve().parents[2]       # <book>/lecture/slides/common.py
BOOK = _BOOKDIR.as_uri()                               # file:// URL of the book directory
with open(_BOOKDIR / "book.toml", "rb") as _f:
    AUTHOR = tomllib.load(_f)["book"]["author"]
COVER = f"{BOOK}/cover.png" if (_BOOKDIR / "cover.png").exists() else f"{BOOK}/cover.svg"


def esc(text):
    return _html.escape(text, quote=False)


def card(x, y, w, h, title, body, s=1, accent=NAVY):
    return (f'<div class="card" data-s="{s}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
            f'border-top-color:{accent}"><div class="ct" style="color:{accent}">{title}</div>'
            f'<div class="cb">{body}</div></div>')


def stat(x, num, label, unit="", s=1, top=300, width=540):
    u = f'<span class="unit">{unit}</span>' if unit else ""
    return (f'<div class="stat" data-s="{s}" style="left:{x}px;top:{top}px;width:{width}px">'
            f'<div class="num">{num}{u}</div><div class="lab">{label}</div></div>')


def callout(text, top=850, s=1):
    return f'<div class="callout" data-s="{s}" style="top:{top}px">{text}</div>'


def bullets(items, top=240, s=1, step_each=False, size=40):
    """items: strings, or (text, subtext). With step_each, item i appears at step s + i."""
    lis = []
    for i, it in enumerate(items):
        text, sub = (it, None) if isinstance(it, str) else it
        st = s + i if step_each else s
        lis.append(f'<li data-s="{st}">{text}' + (f'<span class="sub">{sub}</span>' if sub else "") + "</li>")
    return f'<ul class="pts" style="top:{top}px;font-size:{size}px">{"".join(lis)}</ul>'


def table(headers, rows, top=240, s=1, widths=None, hl=(), num_cols=(), size=32, left=120, width=None):
    """rows: lists of cell HTML; hl: indexes of highlighted rows; num_cols: right-aligned columns.
    With width, the table spans that many px from left; otherwise it takes its content width.
    widths gives the column widths (CSS values)."""
    cols = "".join(f'<col style="width:{w}">' for w in widths) if widths else ""
    th = "".join(f'<th class="{"num" if i in num_cols else ""}">{h}</th>' for i, h in enumerate(headers))
    trs = []
    for r, row in enumerate(rows):
        tds = "".join(f'<td class="{"num" if i in num_cols else ""}">{c}</td>' for i, c in enumerate(row))
        trs.append(f'<tr class="{"hl" if r in hl else ""}">{tds}</tr>')
    # Only a table placed explicitly gets an inline position (modules may patch the style themselves).
    box = "" if width is None and left == 120 else f"left:{left}px;" + (f"width:{width}px;right:auto;" if width else "")
    return (f'<table class="tbl" data-s="{s}" style="top:{top}px;{box}font-size:{size}px"><colgroup>{cols}</colgroup>'
            f'<tr>{th}</tr>{"".join(trs)}</table>')


def flow(boxes, top=300, s=1, step_each=False, height=None, widths=None):
    """boxes: (title, description). Boxes are joined by arrows, left to right.
    widths: optional flex weights per box (default: equal)."""
    parts = []
    for i, (t, d) in enumerate(boxes):
        st = s + i if step_each else s
        if i:
            parts.append(f'<div class="farr" data-s="{st}">→</div>')
        grow = f' style="flex:{widths[i]}"' if widths else ""
        parts.append(f'<div class="fbox" data-s="{st}"{grow}><div class="ft">{t}</div><div class="fd">{d}</div></div>')
    h = f";height:{height}px" if height else ""
    return f'<div class="flow" style="top:{top}px{h}">{"".join(parts)}</div>'


def timeline(events, top=330, s=1, step_each=False, span=None):
    """events: (position 0..1 or seconds with span, time label, description). Every other label sits below."""
    parts = ['<div class="axis"></div>']
    for i, (pos, t, d) in enumerate(events):
        x = pos / span if span else pos
        st = s + i if step_each else s
        alt = " alt" if i % 2 else ""
        parts.append(f'<div class="ev{alt}" data-s="{st}" style="left:{100 * x:.1f}%"><div class="dot"></div>'
                     f'<div class="t">{t}</div><div class="d">{d}</div></div>')
    return f'<div class="tl" style="top:{top}px">{"".join(parts)}</div>'


def code(text, top=260, s=1, size=30):
    """Monospace block; text is escaped. Wrap words in [[c:...]] or [[k:...]] for comment or keyword colors."""
    t = esc(text)
    for tag in ("c", "k"):
        t = t.replace(f"[[{tag}:", f'<span class="{tag}">')
    t = t.replace("]]", "</span>")
    return f'<div class="code" data-s="{s}" style="top:{top}px;font-size:{size}px">{t}</div>'


def bookfig(name, x, y, w=None, h=None, s=1, caption=None):
    """A figure of the book (book/figures/<name>), e.g. "fig-2-1-components.drawio.svg"."""
    size = (f"width:{w}px;" if w else "") + (f"height:{h}px;" if h else "")
    cap = ""
    if caption:
        cap = f'<div class="figcap" data-s="{s}" style="left:{x}px;top:{y + (h or 0) + 8}px">{caption}</div>'
    return f'<img class="bookfig" data-s="{s}" src="{BOOK}/figures/{name}" style="left:{x}px;top:{y}px;{size}">{cap}'


def note(text, x=120, y=1000, s=1):
    return f'<div class="note" data-s="{s}" style="left:{x}px;top:{y}px">{text}</div>'


def title_slide(kicker, title, sub, note_text, steps):
    return dict(title="", html=f'''
<img class="cover" src="{COVER}">
<div class="title-block">
  <div class="tb-kicker">{kicker}</div>
  <div class="tb-title" style="font-size:110px">{title}</div>
  <div class="tb-sub">{sub}</div>
  <div class="tb-author" data-s="2">{AUTHOR}</div>
  <div class="tb-note" data-s="2">{note_text}</div>
</div>''', steps=steps)
