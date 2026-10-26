"""Render a one-page specimen of the print template (tools/book.css).

The page uses an excerpt of a chapter (work/template-sample.md) so that one
page shows the running head, page number, a section heading, body text, a
table, a figure with caption, an invariant and a code listing. It is laid
out with Paged.js and the TrueType fonts, like the book (tools/build_pdf.py).
"""

import html as H
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pdf as B  # noqa: E402
from make_fonts import make_fonts  # noqa: E402

B.BUILD.mkdir(exist_ok=True)
if (B.BUILD / "figures").exists():
    shutil.rmtree(B.BUILD / "figures")
shutil.copytree(B.BOOK / "figures", B.BUILD / "figures", ignore=shutil.ignore_patterns("src"))
text = (B.BOOK / "work" / "template-sample.md").read_text(encoding="utf-8")
toc = []
body = B.convert("ch", "sample", text, [], toc, "s")
heads = B.bookconf.conf().get("sample", {}).get("heads", ["", ""])   # right-page head, left-page head
css = make_fonts(H.unescape(re.sub(r"<[^>]+>", "", body)) + "".join(heads), B.BUILD / "fonts") + "\n"
css += (B.BOOK / "tools" / "book.css").read_text(encoding="utf-8")
css += f'\n#sample {{ page: sample; break-before: auto; }}'
css += f'\n@page sample:right {{ @top-right {{ content: "{heads[0]}"; }} }}'
css += f'\n@page sample:left {{ @top-left {{ content: "{heads[1]}"; }} }}'
from pygments.formatters import HtmlFormatter  # noqa: E402
css += "\n" + HtmlFormatter(style="friendly").get_style_defs(".hl") + "\n.hl .err { border: none; }"
doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>템플릿 견본</title><style>{css}</style>'
       "<script>window.PagedConfig = { auto: true, after: (flow) => { window.__pagedDone = flow.total; } };</script>"
       '<script src="../tools/vendor/pagedjs/paged.polyfill.js"></script>'
       f'</head><body><section id="sample" class="ch body-start">{B.number_blocks(body)}</section></body></html>')
(B.BUILD / "sample.html").write_text(doc, encoding="utf-8")
pdf = B.BUILD / "template-sample.pdf"
B.layout(B.BUILD / "sample.html", pdf, B.BUILD / "template-sample-qa.txt")
pages = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
print(pdf, [l for l in pages.splitlines() if l.startswith(("Pages", "Page size"))])
