"""Build .drawio.svg figures for the book.

A figure is described once in Python and written as one SVG file that
also carries the draw.io model in its `content` attribute, so GitHub and
Obsidian show it as an image and draw.io opens it for editing.

Every cell uses absolute coordinates under the root layer, and every
edge has explicit exit and entry points with the perimeter turned off
and `edgeStyle=none`. That keeps draw.io's rendering of the model the
same polyline that this module draws into the SVG.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

FONT = "Helvetica"
SVG_FONT = "Helvetica, Arial, 'Noto Sans', sans-serif"
FS = 12          # node label size
EFS = 12         # edge label size
LINE = 1.25      # line height factor
INK = "#333333"
SOFT = "#666666"
PAPER = "#FFFFFF"
GROUP_FILL = "#F5F5F5"
HI_FILL = "#DAE8FC"
HI_INK = "#1F4E79"
CHAR_W = 0.58    # average glyph width in em, used only to warn about overflow
# Print rule: a figure is scaled to the text width (140 mm for a 183 x 235 mm
# computer book). 12 px text on a canvas at most 680 px wide prints at 7 pt or more.
MAX_W = 680
MIN_FONT = 12


@dataclass
class Box:
    id: str
    x: float
    y: float
    w: float
    h: float
    label: str
    shape: str = "rect"   # rect, round, group, db, ellipse, folder, note, text, label, anchor
    hi: bool = False
    bold: bool = False
    fill: str | None = None
    dashed: bool = False
    size: int = FS
    align: str = "center"  # text shapes; "left" or "right" for group labels

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


@dataclass
class Edge:
    id: str
    src: str
    tgt: str
    label: str = ""
    kind: str = "solid"     # solid, dashed, thick, line and dashline (no arrow)
    points: list = field(default_factory=list)
    exit: tuple | None = None    # relative (0..1, 0..1) on source bbox
    entry: tuple | None = None
    both: bool = False
    hi: bool = False
    label_at: float = 0.5        # position along the path, 0..1
    label_dx: float = 0
    label_dy: float = 0


class Fig:
    def __init__(self, w: int, h: int, name: str):
        self.w, self.h, self.name = w, h, name
        self.boxes: dict[str, Box] = {}
        self.order: list[str] = []
        self.edges: list[Edge] = []

    # ---- building -------------------------------------------------------
    def box(self, id, x, y, w, h, label, shape="rect", **kw):
        b = Box(id, x, y, w, h, label, shape, **kw)
        self.boxes[id] = b
        self.order.append(id)
        return b

    def group(self, id, x, y, w, h, label, **kw):
        return self.box(id, x, y, w, h, label, "group", **kw)

    def text(self, id, x, y, w, h, label, **kw):
        return self.box(id, x, y, w, h, label, "text", **kw)

    def edge(self, src, tgt, label="", **kw):
        e = Edge(f"e{len(self.edges) + 1}", src, tgt, label, **kw)
        self.edges.append(e)
        return e

    # ---- geometry -------------------------------------------------------
    def _anchor(self, b: Box, rel, toward):
        if rel is not None:
            return b.x + rel[0] * b.w, b.y + rel[1] * b.h
        tx, ty = toward
        dx, dy = tx - b.cx, ty - b.cy
        if dx == 0 and dy == 0:
            return b.cx, b.cy
        if b.shape == "ellipse":
            a, c = b.w / 2, b.h / 2
            t = 1 / math.sqrt((dx / a) ** 2 + (dy / c) ** 2)
            return b.cx + dx * t, b.cy + dy * t
        tx_ = (b.w / 2) / abs(dx) if dx else math.inf
        ty_ = (b.h / 2) / abs(dy) if dy else math.inf
        t = min(tx_, ty_)
        return b.cx + dx * t, b.cy + dy * t

    def _path(self, e: Edge):
        s, t = self.boxes[e.src], self.boxes[e.tgt]
        first = e.points[0] if e.points else (t.cx, t.cy)
        last = e.points[-1] if e.points else (s.cx, s.cy)
        p0 = self._anchor(s, e.exit, first)
        p1 = self._anchor(t, e.entry, last)
        return [p0, *e.points, p1]

    @staticmethod
    def _point_at(path, frac):
        segs = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
        lens = [math.dist(a, b) for a, b in segs]
        goal = sum(lens) * frac
        for (a, b), l in zip(segs, lens):
            if goal <= l and l > 0:
                r = goal / l
                return a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r
            goal -= l
        return path[-1]

    # ---- SVG ------------------------------------------------------------
    def _svg_text(self, x, y, lines, size, anchor="middle", weight="normal", color=INK):
        n = len(lines)
        lh = size * LINE
        y0 = y - (n - 1) * lh / 2
        out = []
        for i, ln in enumerate(lines):
            out.append(
                f'<text x="{x:.1f}" y="{y0 + i * lh:.1f}" font-family="{SVG_FONT}" '
                f'font-size="{size}" font-weight="{weight}" fill="{color}" '
                f'text-anchor="{anchor}" dominant-baseline="central">{escape(ln)}</text>')
        return out

    def _svg_box(self, b: Box):
        ink = HI_INK if b.hi else (SOFT if b.shape == "group" else INK)
        fill = b.fill or (HI_FILL if b.hi else (GROUP_FILL if b.shape == "group" else PAPER))
        sw = 2.5 if b.hi else 1
        dash = ' stroke-dasharray="6 4"' if b.dashed else ""
        common = f'fill="{fill}" stroke="{ink}" stroke-width="{sw}"{dash}'
        x, y, w, h = b.x, b.y, b.w, b.h
        out = []
        if b.shape == "anchor":
            return out
        if b.shape == "label":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PAPER}" stroke="none"/>')
            lines = b.label.split("\n")
            out += self._svg_text(x + 3, b.cy, lines, b.size, anchor="start", color=INK)
            return out
        if b.shape in ("rect", "round", "group"):
            rx = {"rect": 0, "round": 8, "group": 6}[b.shape]
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {common}/>')
        elif b.shape == "db":
            ry = 8
            out.append(
                f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0 1 {x + w},{y + ry} L{x + w},{y + h - ry} '
                f'A{w / 2},{ry} 0 0 1 {x},{y + h - ry} Z" {common}/>')
            out.append(
                f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0 0 {x + w},{y + ry}" fill="none" '
                f'stroke="{ink}" stroke-width="{sw}"/>')
        elif b.shape == "ellipse":
            out.append(f'<ellipse cx="{b.cx}" cy="{b.cy}" rx="{w / 2}" ry="{h / 2}" {common}/>')
        elif b.shape == "folder":
            tw, th = min(48, w * 0.3), 10
            out.append(
                f'<path d="M{x},{y + th} L{x},{y + 2} Q{x},{y} {x + 2},{y} L{x + tw - 6},{y} '
                f'L{x + tw},{y + th} L{x + w},{y + th} L{x + w},{y + h} L{x},{y + h} Z" {common}/>')
        elif b.shape == "note":
            f = 12
            out.append(
                f'<path d="M{x},{y} L{x + w - f},{y} L{x + w},{y + f} L{x + w},{y + h} L{x},{y + h} Z" {common}/>')
            out.append(
                f'<path d="M{x + w - f},{y} L{x + w - f},{y + f} L{x + w},{y + f}" fill="none" '
                f'stroke="{ink}" stroke-width="{sw}"/>')
        lines = b.label.split("\n") if b.label else []
        weight = "bold" if (b.bold or b.hi or b.shape == "group") else "normal"
        if b.shape in ("group",) or (b.shape == "folder" and b.align == "top"):
            top = y + (10 if b.shape == "folder" else 0) + 6 + b.size * LINE * len(lines) / 2
            if b.align == "right":
                out += self._svg_text(x + w - 8, top, lines, b.size, anchor="end", weight=weight, color=ink)
            else:
                out += self._svg_text(x + 8, top, lines, b.size, anchor="start", weight=weight, color=ink)
        elif b.shape == "text":
            anchor = {"left": "start", "center": "middle", "right": "end"}[b.align]
            tx = {"left": x, "center": b.cx, "right": x + w}[b.align]
            out += self._svg_text(tx, b.cy, lines, b.size, anchor=anchor, weight=weight, color=ink)
        else:
            cy = b.cy + (4 if b.shape == "db" else 0) + (5 if b.shape == "folder" else 0)
            out += self._svg_text(b.cx, cy, lines, b.size, weight=weight, color=ink)
        return out

    def _svg_edge(self, e: Edge):
        path = self._path(e)
        ink = HI_INK if e.hi else INK
        sw = {"thick": 2.5, "solid": 1.2, "dashed": 1.2, "line": 1.2, "dashline": 1.2}[e.kind]
        if e.hi:
            sw = round(sw * 1.5, 2)
        dash = ' stroke-dasharray="6 4"' if e.kind in ("dashed", "dashline") else ""
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in path)
        out = [f'<polyline points="{pts}" fill="none" stroke="{ink}" stroke-width="{sw}"{dash}/>']
        if e.kind not in ("line", "dashline"):
            out.append(self._arrow(path[-2], path[-1], ink))
            if e.both:
                out.append(self._arrow(path[1], path[0], ink))
        if e.label:
            lx, ly = self._point_at(path, e.label_at)
            lx += e.label_dx
            ly += e.label_dy
            lines = e.label.split("\n")
            wmax = max(max(len(l) for l in lines) * EFS * (0.6 if e.hi else 0.56) + 8, 30)
            hh = len(lines) * EFS * LINE + 2
            out.append(f'<rect x="{lx - wmax / 2:.1f}" y="{ly - hh / 2:.1f}" width="{wmax:.1f}" '
                       f'height="{hh:.1f}" fill="{PAPER}" stroke="none"/>')
            out += self._svg_text(lx, ly, lines, EFS, color=ink, weight="bold" if e.hi else "normal")
        return out

    @staticmethod
    def _arrow(a, b, ink, size=9):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        w = size * 0.45
        p1 = (b[0] - size * math.cos(ang) + w * math.sin(ang), b[1] - size * math.sin(ang) - w * math.cos(ang))
        p2 = (b[0] - size * math.cos(ang) - w * math.sin(ang), b[1] - size * math.sin(ang) + w * math.cos(ang))
        return (f'<polygon points="{b[0]:.1f},{b[1]:.1f} {p1[0]:.1f},{p1[1]:.1f} '
                f'{p2[0]:.1f},{p2[1]:.1f}" fill="{ink}" stroke="{ink}"/>')

    # ---- draw.io model --------------------------------------------------
    def _style_box(self, b: Box):
        ink = HI_INK if b.hi else (SOFT if b.shape == "group" else INK)
        fill = b.fill or (HI_FILL if b.hi else (GROUP_FILL if b.shape == "group" else PAPER))
        base = {
            "rect": "rounded=0;whiteSpace=wrap;",
            "round": "rounded=1;arcSize=12;whiteSpace=wrap;",
            "group": "rounded=1;arcSize=3;whiteSpace=wrap;verticalAlign=top;align=left;spacingLeft=8;spacingTop=2;",
            "db": "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=8;whiteSpace=wrap;",
            "ellipse": "ellipse;whiteSpace=wrap;",
            "folder": "shape=folder;tabWidth=48;tabHeight=10;tabPosition=left;whiteSpace=wrap;",
            "note": "shape=note;size=12;whiteSpace=wrap;",
            "text": f"text;strokeColor=none;fillColor=none;align={b.align};verticalAlign=middle;",
            "label": "text;strokeColor=none;fillColor=#FFFFFF;align=left;verticalAlign=middle;spacingLeft=3;whiteSpace=wrap;",
            "anchor": "text;strokeColor=none;fillColor=none;",
        }[b.shape]
        if b.shape == "group" and b.align == "right":
            base = base.replace("align=left;spacingLeft=8;", "align=right;spacingRight=8;")
        if b.shape == "folder" and b.align == "top":
            base += "verticalAlign=top;align=left;spacingLeft=8;spacingTop=10;"
        bold = b.bold or b.hi or b.shape == "group"
        st = base + f"html=1;fontFamily={FONT};fontSize={b.size};fontColor={ink};"
        if b.shape not in ("text", "label", "anchor"):
            st += f"fillColor={fill};strokeColor={ink};strokeWidth={2.5 if b.hi else 1};"
        if b.dashed:
            st += "dashed=1;"
        if bold:
            st += "fontStyle=1;"
        return st

    def _style_edge(self, e: Edge, path):
        ink = HI_INK if e.hi else INK
        sw = {"thick": 2.5, "solid": 1.2, "dashed": 1.2, "line": 1.2, "dashline": 1.2}[e.kind]
        if e.hi:
            sw = round(sw * 1.5, 2)
        st = (f"edgeStyle=none;html=1;rounded=0;strokeColor={ink};strokeWidth={sw};"
              f"fontFamily={FONT};fontSize={EFS};fontColor={ink};labelBackgroundColor={PAPER};"
              "exitPerimeter=0;entryPerimeter=0;")
        st += "endArrow=none;" if e.kind in ("line", "dashline") else "endArrow=block;endFill=1;endSize=8;"
        st += "startArrow=block;startFill=1;startSize=8;" if e.both else "startArrow=none;"
        if e.kind in ("dashed", "dashline"):
            st += "dashed=1;dashPattern=6 4;"
        if e.hi:
            st += "fontStyle=1;"
        s, t = self.boxes[e.src], self.boxes[e.tgt]
        (x0, y0), (x1, y1) = path[0], path[-1]
        st += f"exitX={(x0 - s.x) / s.w:.4f};exitY={(y0 - s.y) / s.h:.4f};exitDx=0;exitDy=0;"
        st += f"entryX={(x1 - t.x) / t.w:.4f};entryY={(y1 - t.y) / t.h:.4f};entryDx=0;entryDy=0;"
        return st

    def _model(self):
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        for bid in self.order:
            b = self.boxes[bid]
            val = escape(b.label).replace("\n", "&lt;br&gt;")
            cells.append(
                f'<mxCell id="{bid}" value="{val}" style="{self._style_box(b)}" vertex="1" parent="1">'
                f'<mxGeometry x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" as="geometry"/></mxCell>')
        for e in self.edges:
            path = self._path(e)
            val = escape(e.label).replace("\n", "&lt;br&gt;")
            pts = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in e.points)
            arr = f'<Array as="points">{pts}</Array>' if pts else ""
            # draw.io places a label at relative x in -1..1 along the edge; 0 is the middle.
            rel = e.label_at * 2 - 1
            off = (f'<mxPoint x="{e.label_dx}" y="{e.label_dy}" as="offset"/>'
                   if (e.label_dx or e.label_dy) else "")
            cells.append(
                f'<mxCell id="{e.id}" value="{val}" style="{self._style_edge(e, path)}" edge="1" parent="1" '
                f'source="{e.src}" target="{e.tgt}"><mxGeometry x="{rel:.3f}" relative="1" as="geometry">'
                f'{arr}{off}</mxGeometry></mxCell>')
        model = (f'<mxGraphModel dx="{self.w}" dy="{self.h}" grid="1" gridSize="10" guides="1" '
                 f'tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" '
                 f'pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
                 f'<root>{"".join(cells)}</root></mxGraphModel>')
        return (f'<mxfile host="drawio_fig.py" type="device"><diagram id="{self.name}" '
                f'name="{self.name}">{model}</diagram></mxfile>')

    # ---- checks and output ---------------------------------------------
    def _check(self):
        warn = []
        if self.w > MAX_W:
            warn.append(f"{self.name}: canvas is {self.w} px wide, more than {MAX_W} px (text would print below 7 pt)")
        for b in self.boxes.values():
            if b.label and b.size < MIN_FONT:
                warn.append(f"{self.name}: {b.id} uses {b.size} px text, less than {MIN_FONT} px")
            lines = b.label.split("\n") if b.label else []
            if not lines or b.shape in ("text", "anchor"):
                continue
            need = max(len(l) for l in lines) * b.size * CHAR_W + 12
            if need > b.w:
                warn.append(f"{self.name}: label of {b.id} may overflow ({need:.0f} > {b.w})")
            pad = 4 if b.shape == "label" else 8   # a label has no border to clear
            if b.shape not in ("group",) and len(lines) * b.size * LINE + pad > b.h:
                warn.append(f"{self.name}: label of {b.id} may be too tall")
            if b.x < 0 or b.y < 0 or b.x + b.w > self.w or b.y + b.h > self.h:
                warn.append(f"{self.name}: {b.id} is outside the canvas")
        for e in self.edges:
            for end in (e.src, e.tgt):
                if end not in self.boxes:
                    warn.append(f"{self.name}: edge {e.id} refers to unknown {end}")
        return warn

    def write(self, path: Path):
        warn = self._check()
        for w in warn:
            print("warning:", w, file=sys.stderr)
        body = []
        groups = [i for i in self.order if self.boxes[i].shape == "group"
                  or (self.boxes[i].shape == "folder" and self.boxes[i].align == "top")]
        rest = [i for i in self.order if i not in groups]
        for bid in groups:
            body += self._svg_box(self.boxes[bid])
        for e in self.edges:
            body += self._svg_edge(e)
        for bid in rest:
            body += self._svg_box(self.boxes[bid])
        content = escape(self._model(), quote=True)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{self.w}" '
               f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" content="{content}">'
               f'<rect width="100%" height="100%" fill="{PAPER}"/>' + "".join(body) + "</svg>\n")
        path.write_text(svg, encoding="utf-8")
        return warn
