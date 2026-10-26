"""Replace PlantUML figure blocks with the matching .drawio.svg image.

A block is replaced when its `' 그림 N.M 제목` comment names a figure that
has a file figures/fig-N-M-*.drawio.svg. The image line keeps the caption
as its alt text: ![그림 N.M 제목](figures/fig-N-M-name.drawio.svg)
"""

import re
import sys
from pathlib import Path

BOOK = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"```plantuml\n(.*?)```\n", re.S)
CAPTION = re.compile(r"^' (그림 (\d+)\.(\d+) .+)$", re.M)


def figure_files():
    out = {}
    for f in (BOOK / "figures").glob("fig-*.drawio.svg"):
        m = re.match(r"fig-(\d+)-(\d+)-", f.name)
        if m:
            key = (int(m.group(1)), int(m.group(2)))
            if key in out:
                sys.exit(f"two files for figure {key}: {out[key]} and {f.name}")
            out[key] = f.name
    return out


def main():
    files = figure_files()
    done = set()
    for doc in sorted(BOOK.glob("ch*.md")):
        text = doc.read_text(encoding="utf-8")

        def repl(m):
            cap = CAPTION.search(m.group(1))
            if not cap:
                return m.group(0)
            key = (int(cap.group(2)), int(cap.group(3)))
            if key not in files:
                return m.group(0)
            done.add(key)
            return f"![{cap.group(1).strip()}](figures/{files[key]})\n"

        new = BLOCK.sub(repl, text)
        if new != text:
            doc.write_text(new, encoding="utf-8")
    missing = sorted(set(files) - done)
    already = [k for k in missing if any(
        f"(figures/{files[k]})" in d.read_text(encoding="utf-8") for d in BOOK.glob("ch*.md"))]
    for k in missing:
        if k not in already:
            print(f"warning: no PlantUML block for figure {k[0]}.{k[1]} ({files[k]})", file=sys.stderr)
    print(f"replaced {len(done)} blocks, {len(already)} already embedded")


if __name__ == "__main__":
    main()
