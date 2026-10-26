"""Component figure of the structure chapter and the location figures N.1.

Example from the 3FS book (figure 2.1). Copy it to figures/src/components.py
and replace the boxes, edges, LABELS and CHAPTERS with this book's own. Every
location figure reuses the one layout in build() and changes only what is
highlighted, so a reader finds the same box in the same place in every chapter.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from drawio_fig import Fig  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
BASE = "fig-2-1-components"

# Edge labels of the base figure, keyed by (source, target).
LABELS = {
    ("App", "Fuse"): "POSIX read/write\nor USRBIO",
    ("Fuse", "Meta"): "lookup, create,\nclose",
    ("Fuse", "Mgmtd"): "routing info\n(pull every 10 s)",
    ("Fuse", "Storage"): "chunk read / write\n(RDMA)",
    ("Storage", "Storage"): "forward along chain",
    ("Storage", "SSD"): "",
    ("Meta", "FDB"): "",
    ("Mgmtd", "FDB"): "",
    ("Storage", "Mgmtd"): "heartbeat",
    ("Meta", "Mgmtd"): "heartbeat",
    ("Storage", "Mon"): "metrics",
    ("Mon", "CH"): "",
}

# Chapter number -> what its location figure highlights. "labels" replaces an
# edge label in that chapter's figure only. Start from the code paths in the
# design's per-chapter plan and apply the writers' proposals from their notes.
CHAPTERS = {
    7: {"nodes": ["Meta", "FDB"], "edges": [("Fuse", "Meta"), ("Meta", "FDB")],
        "labels": {("Meta", "FDB"): "transactions"}},
    8: {"nodes": ["Storage"], "edges": [("Storage", "Storage")]},
    13: {"nodes": ["Mon", "CH"], "edges": [("Storage", "Mon"), ("Mon", "CH")]},
}


def build(name, nodes=(), edges=(), labels=None):
    lab = dict(LABELS)
    for key in list(edges) + list(labels or {}):
        if key not in LABELS:
            raise SystemExit(f"{name}: unknown edge {key}")
    lab.update(labels or {})
    hi_edges = set(edges)

    # 680 px wide with 12 px text, so the figure prints at 7 pt or more.
    f = Fig(680, 630, name)
    f.group("gMeta", 20, 20, 640, 200, "meta node")
    f.group("gClient", 70, 290, 540, 120, "gpu1 (client node)")
    f.group("gStorage", 20, 460, 640, 160, "storage1 ~ storage5")

    def node(id, *a, **kw):
        return f.box(id, *a, hi=id in nodes, **kw)

    node("Mgmtd", 170, 150, 110, 40, "mgmtd", shape="round")
    node("Meta", 380, 150, 110, 40, "meta", shape="round")
    node("FDB", 250, 46, 160, 66, "FoundationDB", shape="db")
    node("CH", 537, 46, 100, 66, "ClickHouse", shape="db")
    node("Mon", 520, 150, 135, 40, "monitor_collector", shape="round")
    node("App", 90, 340, 120, 44, "Application", shape="round")
    node("Fuse", 360, 324, 190, 72, "FUSE client\nhf3fs_fuse_main\n(storage client, USRBIO)", shape="round")
    node("SSD", 150, 492, 110, 70, "SSD x 16", shape="db")
    node("Storage", 355, 500, 200, 56, "storage service\n(CRAQ, chunk engine)", shape="round")

    # Explicit exit and entry points and bend points keep lines off boxes and
    # labels; thick lines are the data path, dashed lines are control traffic.
    def e(src, tgt, **kw):
        return f.edge(src, tgt, lab[(src, tgt)], hi=(src, tgt) in hi_edges, **kw)

    e("App", "Fuse", exit=(1, 0.5), entry=(0, 38 / 72))
    e("Fuse", "Meta", exit=(0.5, 0), entry=(75 / 110, 1), label_at=0.45)
    e("Fuse", "Mgmtd", kind="dashed", exit=(28.5 / 190, 0), entry=(60 / 110, 1),
      points=[(388.5, 244), (230, 244)], label_at=0.5)
    e("Fuse", "Storage", kind="thick", exit=(0.5, 1), entry=(0.5, 0), label_at=0.33)
    e("Storage", "Storage", kind="thick", exit=(0.1, 1), entry=(0.9, 1),
      points=[(375, 600), (535, 600)])
    e("Storage", "SSD", exit=(0, 0.5), entry=(1, 36 / 70))
    e("Meta", "FDB", exit=(0.2, 0), entry=(152 / 160, 1))
    e("Mgmtd", "FDB", exit=(0.8, 0), entry=(8 / 160, 1))
    e("Storage", "Mgmtd", kind="dashed", exit=(0.1, 0), entry=(0, 0.5),
      points=[(375, 440), (40, 440), (40, 170)], label_at=0.38)
    e("Meta", "Mgmtd", kind="dashed", exit=(0, 0.5), entry=(1, 0.5))
    e("Storage", "Mon", kind="dashed", exit=(1, 15 / 56), entry=(67.5 / 135, 1),
      points=[(635, 515), (635, 240), (587.5, 240)], label_at=0.3425)
    e("Mon", "CH", exit=(0.5, 0), entry=(0.5, 1))
    return f


if __name__ == "__main__":
    warned = build(BASE).write(OUT / f"{BASE}.drawio.svg")
    for ch, spec in CHAPTERS.items():
        name = f"fig-{ch}-1-location"
        warned += build(name, spec["nodes"], spec["edges"], spec.get("labels")).write(OUT / f"{name}.drawio.svg")
    print(f"{1 + len(CHAPTERS)} figures, {len(warned)} warnings")
