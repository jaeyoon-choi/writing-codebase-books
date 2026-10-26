"""Measure how large each PlantUML figure prints with the book template.

Renders every PlantUML block (or the figures named on the command line,
e.g. 4.4 13.4) with the print style of build_pdf.py and applies the
template's sizing: PRINT_W px span the 143 mm text width, narrower
figures scale by the same factor, and a figure taller than 178 mm is
shrunk to fit. Reports the smallest printed text size and the printed
height. Exit status 1 if any figure prints text under 7 pt.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pdf as B  # noqa: E402

TEXT_W, MAX_H, MIN_PT = 143.0, 178.0, 7.0


def blocks():
    for f in [B.BOOK / name for kind, name in B.bookconf.written_order()]:
        for m in B.PUML.finditer(f.read_text(encoding="utf-8")):
            cap = re.search(r"^' 그림 ([\d.]+) (.+)$", m.group(1), re.M)
            yield (cap.group(1) if cap else f.name), (cap.group(2) if cap else ""), m.group(1)


def main():
    want = set(sys.argv[1:])
    items = [b for b in blocks() if not want or b[0] in want]
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for num, _, src in items:
            p = Path(d) / f"f{num.replace('.', '_')}.puml"
            p.write_text(B.with_print_style(src), encoding="utf-8")
            paths.append(p)
        subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(B.DEFAULT_JAR), "-tsvg", "-charset", "UTF-8",
                        *map(str, paths)], check=True, stdout=subprocess.DEVNULL)
        bad = 0
        rows = []
        for (num, title, _), p in zip(items, paths):
            t = p.with_suffix(".svg").read_text(encoding="utf-8")
            w = float(re.search(r'<svg[^>]*?width="([\d.]+)px"', t).group(1))
            h = float(re.search(r'<svg[^>]*?height="([\d.]+)px"', t).group(1))
            font = min(float(x) for x in re.findall(r'font-size="([\d.]+)"', t))
            width_mm = TEXT_W * min(w, B.PRINT_W) / B.PRINT_W
            height_mm = h * width_mm / w
            shrink = min(1.0, MAX_H / height_mm)
            pt = font * width_mm / w * shrink / 0.3528
            ok = pt >= MIN_PT
            bad += not ok
            rows.append((pt, num, w, h, height_mm * shrink, ok, title))
        for pt, num, w, h, hm, ok, title in sorted(rows):
            print(f"{'OK ' if ok else 'LOW'} {num:>6} {pt:4.1f}pt  {w:5.0f}x{h:<5.0f}px  {hm:5.0f}mm  {title[:40]}")
        print(f"{len(rows)} figures, {bad} below {MIN_PT} pt")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
