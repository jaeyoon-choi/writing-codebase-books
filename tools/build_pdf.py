"""Typeset the whole manuscript into a PDF with Paged.js in headless Chrome.

Page: 183 x 235 mm (a common computer-book trim), text width 143 mm.
PlantUML blocks are rendered to SVG with the PlantUML jar (cached by
content hash) and draw.io figures are embedded as images. The CJK fonts
are converted to TrueType (tools/make_fonts.py) so that the PDF has no
Type 3 fonts. Paged.js (tools/vendor/pagedjs) lays out the pages; then
this script fills in the page numbers of the table of contents, checks
every page (tools/qa_pages.js) and prints the PDF over the Chrome DevTools
protocol.

Usage: python3 -I tools/build_pdf.py [--print] [--jar PATH] [--out PATH]
  --print  printer's PDF without the cover, with 3 mm bleed, crop marks and TrimBox
"""

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import markdown
import websocket

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconf  # noqa: E402
from make_fonts import make_fonts  # noqa: E402
from pdf_boxes import set_boxes  # noqa: E402

BOOK = Path(__file__).resolve().parents[1]
BUILD = BOOK / "build"
DEFAULT_JAR = Path(bookconf.conf().get("figures", {}).get(
    "plantuml_jar", "~/.vscode/extensions/jebbs.plantuml-2.18.1/plantuml.jar")).expanduser()
TITLE = bookconf.book()["title"]

ORDER = bookconf.order()

PUML = re.compile(r"```plantuml\n(.*?)```\n", re.S)

# Print style added to every PlantUML figure when the book is typeset: one text
# size (12 px prints at 7 pt or more when 680 px spans the 143 mm text width),
# wrapped messages and tighter spacing so figures stay narrow.
PRINT_STYLE = """skinparam defaultFontSize 12
skinparam sequenceGroupHeaderFontSize 12
skinparam sequenceGroupFontSize 12
skinparam maxMessageSize 120
skinparam wrapWidth 170
skinparam ParticipantPadding 2
skinparam BoxPadding 2
skinparam nodesep 18
skinparam ranksep 28"""


def with_print_style(src):
    return re.sub(r"^@startuml.*$", lambda m: m.group(0) + "\n" + PRINT_STYLE, src, count=1, flags=re.M)
IMG = re.compile(r"^!\[(그림 [^\]]*)\]\(([^)]+)\)\s*$", re.M)
# A text block whose first line is a figure caption (byte and bit layouts, figures 4.3 and 9.3).
TEXTFIG = re.compile(r"^```\n(그림 \d+\.\d+ [^\n]+)\n(.*?)^```\n", re.S | re.M)


def render_plantuml(blocks, jar):
    """Render PlantUML sources to SVG files under build/plantuml, cached by hash."""
    out = BUILD / "plantuml"
    out.mkdir(parents=True, exist_ok=True)
    todo = []
    names = []
    for src in blocks:
        src = with_print_style(src)
        h = hashlib.sha1(src.encode()).hexdigest()[:16]
        names.append(f"plantuml/{h}.svg")
        if not (out / f"{h}.svg").exists():
            (out / f"{h}.puml").write_text(src, encoding="utf-8")
            todo.append(str(out / f"{h}.puml"))
    if todo:
        print(f"rendering {len(todo)} PlantUML figures", file=sys.stderr)
        subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "-tsvg", "-charset", "UTF-8",
                        *todo], check=True)
        for f in todo:
            Path(f).unlink()
    return names


PRINT_W = 680  # px of figure canvas that maps to the full text width (see tools/drawio_fig.py)


def figure(src, caption):
    """A figure scaled so that PRINT_W px of its canvas spans the text width."""
    cap = html.escape(caption)
    width = ""
    f = BUILD / src
    if f.exists():
        m = re.search(r'<svg[^>]*?\swidth="([\d.]+)(?:px)?"', f.read_text(encoding="utf-8")[:4000])
        if m:
            width = f' style="width: {min(100.0, float(m.group(1)) / PRINT_W * 100):.1f}%"'
    return f'\n<figure class="fig"><img src="{src}" alt="{cap}"{width}><figcaption>{cap}</figcaption></figure>\n'


BREAK_AFTER = re.compile(r"(::|[/_.,:](?=[\w]))")
PATHISH = re.compile(r"[\w.:/-]*[/_:][\w.:/-]+")


def add_breaks(body):
    """Let long paths and identifiers wrap: add <wbr> after /, _, ., :: in text outside <pre> and tags."""
    out = []
    for part in re.split(r"(<pre[\s\S]*?</pre>|<[^>]+>)", body):
        if not part or part.startswith("<"):
            out.append(part)
            continue
        out.append(PATHISH.sub(lambda m: BREAK_AFTER.sub(r"\1<wbr>", m.group(0)) if len(m.group(0)) > 14
                               else m.group(0), part))
    return "".join(out)


def convert(kind, name, text, puml_names, toc, slug):
    # Figures first, so markdown does not touch them.
    i = 0

    def puml(m):
        nonlocal i
        src = m.group(1)
        cap = re.search(r"^' (그림 \d+\.\d+ .+)$", src, re.M)
        r = figure(puml_names.pop(0), cap.group(1) if cap else "")
        i += 1
        return r

    text = PUML.sub(puml, text)
    text = IMG.sub(lambda m: figure(m.group(2), m.group(1)), text)
    textfigs = []

    def textfig(m):
        lines = "".join(f'<div class="ln">{html.escape(line)}</div>' for line in m.group(2).rstrip("\n").split("\n"))
        textfigs.append(f'<figure class="fig textfig"><pre><code>{lines}</code></pre>'
                        f"<figcaption>{html.escape(m.group(1))}</figcaption></figure>")
        return f"\n@@TEXTFIG{len(textfigs) - 1}@@\n\n"
    text = TEXTFIG.sub(textfig, text)

    body = markdown.markdown(text, extensions=["tables", "fenced_code", "codehilite", "sane_lists"],
                             extension_configs={"codehilite": {"css_class": "hl", "guess_lang": False, "linespans": "ln"}})
    # One div per listing line, so that Paged.js breaks a listing only between lines (splitting
    # inside a highlighted token drops the line feeds of the rest). The line feed itself goes:
    # a break token that points at it would skip the tokens before it on the next page.
    body = re.sub(r"<pre[\s\S]*?</pre>",
                  lambda m: re.sub(r'<span id="ln-\d+">', '<div class="ln">', m.group(0)).replace("\n</span>", "</div>"),
                  body)
    body = re.sub(r"<p>@@TEXTFIG(\d+)@@</p>", lambda m: textfigs[int(m.group(1))], body)

    # Boxes: blockquotes that start with a bold label.
    def box(m):
        label = m.group(1)
        cls = "key" if label.startswith("핵심 질문") else "tech" if label.startswith("외부 기술") \
            else "lesson" if label.startswith("설계 교훈") else "quote"
        return f'<blockquote class="box {cls}">\n<p><strong>{label}</strong>'
    body = re.sub(r"<blockquote>\s*<p><strong>([^<]+)</strong>", box, body)
    body = re.sub(r"<p><strong>(불변식 \d+\.\d+)</strong>", r'<p class="invariant"><strong>\1</strong>', body)

    body = add_breaks(body)

    # Headings: give ids, record them for the table of contents.
    def h1(m):
        title = html.unescape(re.sub("<[^>]+>", "", m.group(1)))
        hid = f"{slug}-top"
        if kind == "ch":
            num, rest = title.split(" ", 1)
            toc.append((1, title, hid))
            return (f'<div class="chapter-head" id="{hid}"><div class="ch-num">{num}</div>'
                    f'<h1>{html.escape(rest)}</h1></div>')
        if kind == "part":
            toc.append((0, title, hid))
            num, rest = title.split(" ", 1)
            return f'<div class="part-head" id="{hid}"><div class="part-num">{num}</div><h1>{html.escape(rest)}</h1></div>'
        toc.append((1, title, hid))
        return f'<h1 class="plain-h1" id="{hid}">{html.escape(title)}</h1>'
    body = re.sub(r"<h1>(.*?)</h1>", h1, body, count=1)

    def h2(m):
        title = html.unescape(re.sub("<[^>]+>", "", m.group(1)))
        hid = f"{slug}-{len(toc)}"
        if kind in ("ch", "app"):
            toc.append((2, title, hid))
        return f'<h2 id="{hid}">{m.group(1)}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    return body


def number_blocks(content):
    """Give every p, h2-h4, figure, pre, list, table and box a data-n number, so that layout fixes can target one."""
    n = 0

    def tag(m):
        nonlocal n
        n += 1
        return f'<{m.group(1)} data-n="{n}"{m.group(2)}'
    return re.sub(r"<(p|h2|h3|h4|figure|pre|ul|ol|table|blockquote)([\s>])", tag, content)


def split_listings(content, splits):
    """Cut listing n into two listings after its first `at` lines (the part that fits on a page).

    Paged.js 0.4.3 loses the line at the break when it splits a pre itself, so listings never
    break inside; the second part gets the number n + "b" and can be cut again."""
    for n, at in splits:
        m = re.search(rf'<div class="hl"><pre data-n="{n}"([^>]*)>([\s\S]*?)<code>([\s\S]*?)</code></pre></div>', content)
        if not m:
            continue
        lines = re.findall(r'<div class="ln">[\s\S]*?</div>', m.group(3))
        if not 0 < at < len(lines):
            continue
        head = f'<div class="hl"><pre data-n="{n}" class="cont-next"{m.group(1)}>{m.group(2)}<code>{"".join(lines[:at])}</code></pre></div>'
        tail = f'<div class="hl"><pre data-n="{n}b" class="cont-prev"{m.group(1)}><code>{"".join(lines[at:])}</code></pre></div>'
        content = content[:m.start()] + head + tail + content[m.end():]
    return content


def block_end(content, start):
    """End of the top-level block that starts at content[start:]."""
    m = re.match(r'\s*<(p|ul|ol|table|blockquote|h3|h4|div class="hl")', content[start:])
    tag = m.group(1).split()[0]
    close = "</pre></div>" if tag == "div" else f"</{tag}>"
    depth, pos = 0, start
    while True:
        o = content.find(f"<{tag}", pos) if tag != "div" else -1
        c = content.find(close, pos)
        if o != -1 and o < c:
            depth, pos = depth + 1, o + 1
        else:
            depth, pos = depth - 1, c + len(close)
            if depth <= 0:
                return pos


def move_figures(content, moves):
    """Move each figure below the top-level blocks that directly follow it, as a float would go.

    moves: [(figure number, [numbers of the following blocks that fit before the page end])].
    Only the leading run of blocks that really follow the figure, with nothing between, moves."""
    for fig, blocks in moves:
        m = re.search(rf'\n?<figure data-n="{fig}"[\s\S]*?</figure>\n?', content)
        if not m:
            continue
        end = m.end()
        for n in blocks:
            if not re.match(rf'\s*(<(p|ul|ol|table|blockquote|h3|h4)|<div class="hl"><pre) data-n="{n}"[\s>]', content[end:]):
                break
            end = block_end(content, end)
        if end > m.end():
            content = content[:m.start()] + content[m.end():end] + m.group(0) + content[end:]
    return content


def build_html(jar, print_mode, fixes="", moves=(), splits=()):
    docs = []
    all_puml = []
    for kind, name in ORDER:
        text = (BOOK / name).read_text(encoding="utf-8")
        all_puml += [m.group(1) for m in PUML.finditer(text)]
        docs.append((kind, name, text))
    puml_names = render_plantuml(all_puml, jar)

    toc = []
    sections = []
    page_css = []
    part_title = ""
    first_part = True
    for n, (kind, name, text) in enumerate(docs):
        slug = f"d{n:02d}"
        title = text.splitlines()[0].lstrip("# ").strip()
        if kind == "part":
            part_title = title
        body = convert(kind, name, text, puml_names, toc, slug)
        sid, pname = f"s{n:02d}", f"p{n:02d}"
        page_css.append(f"#{sid} {{ page: {pname}; }}")
        if kind == "part":
            page_css.append(f"@page {pname} {{ @top-left {{ content: none; }} @top-right {{ content: none; }} "
                            f"@bottom-center {{ content: none; }} }}")
        else:
            left = html.escape(part_title if kind == "ch" else TITLE)
            page_css.append(f'@page {pname}:left {{ @top-left {{ content: "{left}"; }} }}')
            page_css.append(f'@page {pname}:right {{ @top-right {{ content: "{html.escape(title)}"; }} }}')
            # No running head on the first page of a chapter, preface or appendix.
            page_css.append(f"@page {pname}:first {{ @top-left {{ content: none; }} @top-right {{ content: none; }} }}")
        if kind == "front":
            page_css.append(f"@page {pname} {{ @bottom-center {{ content: counter(page, lower-roman); }} }}")
        extra = " index" if name == "index.md" else ""
        # The evidence appendix (moved path:line tables) is typeset densely; see book.css.
        extra += " evidence" if "evidence" in name else ""
        extra += " body-start" if kind == "part" and first_part else ""
        first_part = first_part and kind != "part"
        sections.append(f'<section id="{sid}" class="{kind}{extra}">{body}</section>')

    # Table of contents: page numbers are filled in after layout (see fill_toc).
    rows = []
    for level, title, hid in toc:
        rows.append(f'<li class="toc{level}"><a href="#{hid}"><span class="t">{html.escape(title)}</span>'
                    f'<span class="dots"></span><span class="pg"></span></a></li>')
    toc_html = '<section id="toc" class="toc"><h1 class="plain-h1">차례</h1><ul>' + "".join(rows) + "</ul></section>"

    bk = bookconf.book()
    meta = "<br>".join(html.escape(x) for x in bk.get("title_meta", []))
    title_page = (f'<section id="title" class="titlepage"><div class="tp-title">{html.escape(bk["title"])}</div>'
                  f'<div class="tp-sub">{html.escape(bk.get("subtitle", ""))}</div>'
                  f'<div class="tp-author">{html.escape(bk["author"])} 지음</div>'
                  f'<div class="tp-meta">{meta}</div></section>')
    cover = ""
    if not print_mode and (BOOK / "cover.svg").exists():
        # Inline, so that its text uses the TrueType fonts below (text in an <img> SVG would not).
        svg = (BOOK / "cover.svg").read_text(encoding="utf-8")
        svg = re.sub(r'(<svg[^>]*?) width="\d+" height="\d+"', r'\1 width="183mm" height="235mm"', svg, count=1)
        cover = f'<section id="cover" class="cover">{svg}</section>'

    content = number_blocks(f"{cover}{title_page}{toc_html}{''.join(sections)}")
    content = move_figures(split_listings(content, splits), moves)
    plain = html.unescape(re.sub(r"<[^>]+>", "", content)) + "".join(re.findall(r'content: "([^"]*)"', "\n".join(page_css)))
    css = make_fonts(plain, BUILD / "fonts") + "\n"
    css += (BOOK / "tools" / "book.css").read_text(encoding="utf-8") + "\n" + "\n".join(page_css)
    # After the named-page rules, so that a blank page before a recto start has no head or folio.
    css += "\n@page :blank { @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; } }"
    css += "\n" + fixes
    if print_mode:
        css += "\n@page { bleed: 3mm; marks: crop; }"
    from pygments.formatters import HtmlFormatter
    css += "\n" + HtmlFormatter(style="friendly").get_style_defs(".hl")
    css += "\n.hl .err { border: none; }"   # tokens Pygments cannot lex (macro pastes) are not errors
    doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{html.escape(TITLE)}</title>'
           f"<style>{css}</style>"
           "<script>window.PagedConfig = { auto: true, after: (flow) => { window.__pagedDone = flow.total; } };</script>"
           '<script src="../tools/vendor/pagedjs/paged.polyfill.js"></script>'
           f"</head><body>{content}</body></html>")
    return doc, toc


class Chrome:
    """Headless Chrome driven over the DevTools protocol."""

    def __init__(self, profile):
        if profile.exists():
            shutil.rmtree(profile)
        self.proc = subprocess.Popen(
            ["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--remote-debugging-port=0",
             f"--user-data-dir={profile}", "--allow-file-access-from-files", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = profile / "DevToolsActivePort"
        for _ in range(200):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.1)
        port = int(port_file.read_text().split()[0])
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        targets = json.load(opener.open(f"http://127.0.0.1:{port}/json/list"))
        url = next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
        self.ws = websocket.create_connection(url, timeout=900, suppress_origin=True, http_no_proxy=["127.0.0.1"])
        self.n = 0
        self.console = []

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]
            if msg.get("method") == "Runtime.consoleAPICalled":
                args = msg["params"]["args"]
                self.console.append((msg["params"]["type"],
                                     " ".join(str(a.get("value", a.get("description", ""))) for a in args)))

    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:2000])
        return r["result"].get("value")

    def pdf(self, path):
        r = self.call("Page.printToPDF", preferCSSPageSize=True, printBackground=True, transferMode="ReturnAsStream")
        chunks = []
        while True:
            d = self.call("IO.read", handle=r["stream"], size=1 << 20)
            chunks.append(base64.b64decode(d["data"]) if d.get("base64Encoded") else d["data"].encode("latin-1"))
            if d.get("eof"):
                break
        self.call("IO.close", handle=r["stream"])
        Path(path).write_bytes(b"".join(chunks))

    def close(self):
        try:
            self.call("Browser.close")
        except Exception:
            pass
        self.proc.wait(timeout=60)


# Page labels: lower-case roman from the title page, arabic from the first part page. They go
# into the table of contents and into every folio (Paged.js 0.4.3 applies page counter resets
# out of order, so the folios do not use counter(page)).
PAGE_LABELS = """(() => {
  const pages = [...document.querySelectorAll('.pagedjs_page')];
  const at = (el) => el ? pages.indexOf(el.closest('.pagedjs_page')) : -1;
  const title = at(document.querySelector('section.titlepage'));
  const body = at(document.querySelector('section.body-start'));
  const roman = (n) => [['m',1000],['cm',900],['d',500],['cd',400],['c',100],['xc',90],['l',50],['xl',40],
    ['x',10],['ix',9],['v',5],['iv',4],['i',1]].reduce((s, [r, v]) => { while (n >= v) { s += r; n -= v; } return s; }, '');
  const label = (i) => i >= body ? String(i - body + 1) : roman(i - title + 1);
  pages.forEach((pg, i) => {
    const box = pg.querySelector('.pagedjs_margin-bottom-center > .pagedjs_margin-content');
    if (!box) return;
    const c = getComputedStyle(box, '::after').content;
    if (c && c !== 'none' && c !== 'normal') box.dataset.folio = label(i);
  });
  const st = document.createElement('style');
  st.textContent = '.pagedjs_margin-bottom-center > .pagedjs_margin-content::after { content: attr(data-folio) !important; }';
  document.head.appendChild(st);
  let missing = [];
  document.querySelectorAll('section.toc a[href^="#"]').forEach((a) => {
    const i = at(document.getElementById(a.getAttribute('href').slice(1)));
    if (i < 0) { missing.push(a.textContent); return; }
    a.querySelector('.pg').textContent = label(i);
  });
  return {pages: pages.length, title, body, missing};
})()"""


def layout(html_path, pdf_path, report_path):
    chrome = Chrome(BUILD / "chrome-profile")
    try:
        chrome.call("Runtime.enable")
        chrome.call("Page.enable")
        chrome.call("Emulation.setEmulatedMedia", media="print")
        chrome.call("Page.navigate", url=html_path.resolve().as_uri())
        start = time.time()
        while not chrome.eval("window.__pagedDone || 0"):
            if time.time() - start > 1800:
                raise RuntimeError("Paged.js did not finish in 30 minutes")
            time.sleep(2)
        info = chrome.eval(PAGE_LABELS)
        issues = chrome.eval((BOOK / "tools" / "qa_pages.js").read_text(encoding="utf-8"))
        chrome.pdf(pdf_path)
        warnings = [m for kind, m in chrome.console if kind in ("warning", "error")]
    finally:
        chrome.close()
    lines = [f"{i['page']}\t{i['kind']}\t{i['what']}" for i in issues] + [f"-\tconsole\t{w}" for w in warnings]
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return info, issues, warnings, time.time() - start


def fixes_for(issues):
    """Fixes for what the page checks found: a heading alone at the bottom of a page moves to the
    next page, a paragraph with one line on a page stays whole when that costs at most five lines
    of space (as does a block that runs past the page bottom), a figure that left a page mostly
    empty shrinks to fit there when it is at most 5% too tall or else floats below the blocks
    that fit there, a listing that did the same is cut where
    the page ends, a table wider than the text lets its identifiers break anywhere, and a part
    opener that runs onto a second page loses most of its top space. Returns (CSS rules, layout changes)."""
    rules, changes = [], []
    for i in issues:
        if i["kind"] == "part-overflow" and i.get("sid"):
            # Paged.js rewrites #id to [data-id=...], so the class keeps this above section.part.
            rules.append(f'section.part#{i["sid"]} {{ padding-top: 16mm; }}')
        if i.get("paras"):
            changes.append(("move", i["fig"], tuple(i["paras"])))
        if i.get("shrink"):
            rules.append(f'figure.fig[data-n="{i["shrink"]}"] img {{ max-height: {i["maxh"]}mm; }}')
        if i.get("split"):
            changes.append(("split", i["split"], i["at"]))
        if not i.get("n"):
            continue
        if i["kind"] == "heading-at-bottom":
            rules.append(f'[data-n="{i["n"]}"] {{ break-before: page; }}')
        elif i["kind"] == "overflow-x" and i["what"].startswith("table"):
            rules.append(f'table[data-n="{i["n"]}"] code {{ overflow-wrap: anywhere; }}')
        elif i["kind"] == "overflow-y" and i.get("head"):
            rules.append(f'[data-n="{i["head"]}"] {{ break-before: page; }}')
        elif i["kind"] in ("orphan", "overflow-y") or (i["kind"] == "widow" and i.get("before", 99) <= 5):
            rules.append(f'[data-n="{i["n"]}"] {{ break-inside: avoid; }}')
    return rules, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", default=str(DEFAULT_JAR))
    ap.add_argument("--print", dest="print_mode", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.print_mode and bookconf.missing():
        sys.exit(f"build_pdf: missing files in [layout] order: {', '.join(bookconf.missing())}")
    ORDER[:] = bookconf.written_order()
    BUILD.mkdir(exist_ok=True)
    for sub in ("figures",):
        if (BUILD / sub).exists():
            shutil.rmtree(BUILD / sub)
        shutil.copytree(BOOK / sub, BUILD / sub, ignore=shutil.ignore_patterns("src"))
    name = bookconf.book().get("file", "book")
    stem = f"{name}-print" if args.print_mode else name
    pdf = Path(args.out or BUILD / f"{stem}.pdf")
    html_path = BUILD / f"{stem}.html"

    # Lay out, fix what the page checks found, and lay out again (at most five passes).
    fixes, changes = [], []
    for attempt in range(5):
        moves = [c[1:] for c in changes if c[0] == "move"]
        splits = [c[1:] for c in changes if c[0] == "split"]
        doc, toc = build_html(args.jar, args.print_mode, "\n".join(fixes), moves, splits)
        html_path.write_text(doc, encoding="utf-8")
        info, issues, warnings, secs = layout(html_path, pdf, BUILD / f"{stem}-qa.txt")
        rules, found = fixes_for(issues)
        new = [r for r in rules if r not in fixes]
        new_changes = [c for c in found if c not in changes]
        if not new and not new_changes or attempt == 4:
            break
        fixes += new
        changes += new_changes
        print(f"pass {attempt + 1}: {len(new)} break fixes, {len(new_changes)} figure moves and listing cuts",
              file=sys.stderr)
    if args.print_mode:
        set_boxes(pdf, 3.0)
    kinds = {}
    for i in issues:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(f"{pdf} ({info['pages']} pages, layout {secs:.0f} s); TOC entries without a page: {len(info['missing'])}")
    print("page checks:", ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "no issues",
          f"; console warnings: {len(warnings)}; details in {BUILD / (stem + '-qa.txt')}")


if __name__ == "__main__":
    main()
