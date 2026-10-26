"""Compact sequence diagrams on top of drawio_fig.

PlantUML places a message label between the two lifelines it joins, so a
diagram with many participants grows wide. Here every message has its own
row and its label starts at the left end of the arrow and may run over the
lifelines to its right on a white background, which keeps a diagram with
nine participants inside the 680 px print width. Messages keep their order
and are numbered from 1, like PlantUML's autonumber.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawio_fig import CHAR_W, FS, LINE, Fig  # noqa: E402

CHAR = CHAR_W * FS        # average glyph width, as in drawio_fig's overflow check


def sequence(name, participants, messages, groups=(), width=680, col_w=None, left=16, top=16, label_w=330):
    """participants: [(id, label[, shape])] ; messages: [(src, tgt, text, kind)] with kind solid or dashed."""
    n = len(participants)
    col_w = col_w or (width - 2 * left) / n
    xs = {p[0]: left + col_w * i + col_w / 2 for i, p in enumerate(participants)}
    head_lines = max(p[1].count("\n") + 1 for p in participants)
    group_h = 24 if groups else 0
    head_h = head_lines * FS * LINE + 14
    if any(p[2:] == ("db",) for p in participants):
        head_h += 12   # room for the cylinder top
    head_y = top + group_h
    y = head_y + head_h + 18
    rows = []
    for k, (src, tgt, text, kind) in enumerate(messages, 1):
        label = f"{k}. {text}"
        lines = label.count("\n") + 1
        lab_h = lines * FS * LINE + 4
        if src == tgt:
            rows.append((k, src, tgt, label, kind, y, lab_h))
            y += max(lab_h, 22) + 12
        else:
            y += lab_h
            rows.append((k, src, tgt, label, kind, y, lab_h))
            y += 12
    bottom = y + 8
    height = int(bottom + top)
    f = Fig(width, height, name)
    for glabel, ids in groups:
        gx0 = min(xs[i] for i in ids) - col_w / 2 + 2
        gx1 = max(xs[i] for i in ids) + col_w / 2 - 2
        f.group(f"g_{glabel}", gx0, top, gx1 - gx0, bottom - top, glabel)
    for pid, lab, *shape in participants:
        f.box(pid, xs[pid] - col_w / 2 + 4, head_y, col_w - 8, head_h, lab, shape=shape[0] if shape else "rect")
        f.box(f"{pid}_end", xs[pid], bottom, 1, 1, "", shape="anchor")
        f.edge(pid, f"{pid}_end", kind="dashline", exit=(0.5, 1), entry=(0.5, 0.5))
    for k, src, tgt, label, kind, ry, lab_h in rows:
        a, b = f"m{k}a", f"m{k}b"
        if src == tgt:
            x = xs[src]
            f.box(a, x, ry + 4, 1, 1, "", shape="anchor")
            f.box(b, x, ry + 22, 1, 1, "", shape="anchor")
            f.edge(a, b, kind=kind, exit=(0.5, 0.5), entry=(0.5, 0.5), points=[(x + 26, ry + 4), (x + 26, ry + 22)])
            need = max(len(s) for s in label.split("\n")) * CHAR + 13
            if x + 30 + need <= width - 4:
                f.box(f"l{k}", x + 30, ry, need, lab_h, label, shape="label")
            else:
                # Near the right edge the label goes to the left of the lifeline.
                f.box(f"l{k}", x - 6 - need, ry, need, lab_h, label, shape="label")
        else:
            x1, x2 = xs[src], xs[tgt]
            f.box(a, x1, ry, 1, 1, "", shape="anchor")
            f.box(b, x2, ry, 1, 1, "", shape="anchor")
            f.edge(a, b, kind=kind, exit=(0.5, 0.5), entry=(0.5, 0.5))
            lx = min(x1, x2) + 4
            need = max(len(s) for s in label.split("\n")) * CHAR + 13
            if lx + need > width - 4:
                lx = width - 4 - need   # keep the label inside the canvas
            lw = min(max(need, abs(x2 - x1) - 8), width - lx - 4)
            f.box(f"l{k}", lx, ry - lab_h - 2, lw, lab_h, label, shape="label")
    return f
