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
# The manuscript: what the version on the cover describes (not the PDFs that a build rewrites, and not
# README.md, which records where the PDFs are and changes when they are replaced).
MANUSCRIPT = [":(glob)*.md", "figures", ":(exclude)README.md"]


def doc_version():
    """`원고 버전 YYYY.MM.DD HH:MM`: the author time of the last commit that changed the manuscript
    (kept by cherry-pick and rebase, unlike the hash), marked when the working tree has changes that
    commit does not hold. Empty outside a git checkout."""
    git = ["git", "-C", str(BOOK)]
    try:
        last = subprocess.run(git + ["log", "-1", "--date=format:%Y.%m.%d %H:%M", "--format=%ad", "--", *MANUSCRIPT],
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(git + ["status", "--porcelain", "--", *MANUSCRIPT],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    if not last:
        return ""
    return f"원고 버전 {last}" + (" 이후 수정" if dirty else "")


def with_version(svg):
    """The cover SVG with its doc-version element (tools/cover_template.py) filled in."""
    return re.sub(r'(<text id="doc-version"[^>]*>)(</text>)', lambda m: m.group(1) + html.escape(doc_version()) + m.group(2),
                  svg, count=1)

ORDER = bookconf.order()

PUML = re.compile(r"```plantuml\n(.*?)```\n", re.S)

# Print style added to every PlantUML figure when the book is typeset: one text
# size (12 px prints at 7 pt or more when 680 px spans the 143 mm text width),
# wrapped messages and tighter spacing so figures stay narrow. The font is one that
# both Java (which measures the text) and Chrome (which draws it) have; with the
# default sans-serif they pick different fonts and Chrome squeezes the text.
PRINT_STYLE = """skinparam defaultFontName "Noto Sans"
skinparam defaultFontSize 12
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


# From ten characters: a name of 10-14 characters (kMaxSliceSize, IBV_WC_SUCCESS) that cannot break
# moves whole to the next line and leaves wide gaps in the justified line before it.
LONG_TOKEN = re.compile(r"[\w.:/-]{10,}")
# A call such as SERDE_SERVICE(StorageSerde, ...) or LOG(FATAL) may wrap after its parenthesis (never after Hangul).
CALL_PAREN = re.compile(r"(?<=[A-Za-z0-9_]{3})\((?=[A-Za-z_])")
# No break after the dot of a file extension, so that `h` or `cpp` never stands alone on a line: the
# listed extensions, and the last dot of a name when one to five letters and digits end it (.jsonl).
# No break after the :// of a URL either, which would leave `https://` alone at a line end, nor in
# its host (long_token).
EXT = "|".join(bookconf.source().get("extensions", ["h", "cc", "cpp", "py"]) + ["html?"])
# No break after the colon before a line number (`file.cpp:` / `120-130`).
BREAK_AFTER = re.compile(rf"(::|(?<!:/)/(?=\w)|_(?=\w)|:(?=[A-Za-z_])|\.(?!(?:{EXT})(?![A-Za-z0-9]))"
                         r"(?![A-Za-z][A-Za-z0-9]{0,4}(?::[\d,-]+)?\.?$)(?=\w))")
# Between the words of a camelCase name, at least two letters on each side.
CAMEL = re.compile(r"(?<=[a-z0-9]{2})(?=[A-Z][a-z0-9]{2})|(?<=[A-Z]{2})(?=[A-Z][a-z]{2})")
# A commit hash or another hex string, which has no other break point: a break every eight digits.
HEX = re.compile(r"(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{12,}")
UNIT = (r"(?:[KMGTP]i?B(?:/s)?|Gbps|[KMGTP]?FLOPS|[KMG]?Hz|ms|ns|us|µs)(?![A-Za-z])"
        r"|밀리초|마이크로초|나노초|초|분|시간|쪽|장|절|줄|행|개|번|회|건|명|대|배|단계|조각|%|바이트|비트")
NUM_UNIT = rf"\d[\d,.]*(?: ?(?:{UNIT})| [가-힣]{{1,3}})"
# Kept on one line: the -- of a flag with its first word, and a date. (A line range such as
# 1531-1537 may still break after its hyphen: kept whole, it stretches more justified lines.)
NOBR = re.compile(r"(?<![\w-])--[A-Za-z][A-Za-z0-9]*|(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])"
                  # A chapter introduction as a place (9장 도입), like a section number.
                  r"|(?<![\w.])\d+장 도입"
                  # An expression such as 8 × 312 TFLOPS or 99 × 8 × 8 = 6,336개 (see nobr), a number
                  # with its unit or with the start of the Hangul word after it (6.6 TiB/s, 15초, 8.1절,
                  # 512 토큰) and × or = with the number after it.
                  rf"|(?P<expr>(?<![\w.])\d[\d,.]*(?: [×=] (?:{NUM_UNIT}|\d[\d,.]*))+)"
                  rf"|(?<![\w.])(?:[×=] )?{NUM_UNIT}|(?<![\w.])[×=] \d[\d,.]*"
                  # A label with its number and the start of a particle (표 7.2의, 부록 A에), and a short
                  # hyphenated term (NVMe-oF).
                  r"|(?<![가-힣])(?:표|그림|부록|리스팅|불변식) (?:[A-Z]|\d+)(?:\.\d+)*(?![A-Za-z0-9]|\.\d)[가-힣]{0,2}"
                  r"|(?<![\w-])[A-Za-z][A-Za-z0-9]*-[A-Za-z]{1,3}(?![A-Za-z0-9-])"
                  # A line range (5372-5374), which Chrome would otherwise break after the hyphen.
                  r"|(?<![\w.-])\d+-\d+(?![\w-])")


def nobr(m):
    """A NOBR match on one line; an expression longer than 16 characters breaks only before an operator."""
    g = m.group(0)
    if m.group("expr") and len(g) > 16:
        first, *rest = re.split(r" (?=[×=] )", g)
        return first + "".join(f' <span class="nobr">{r}</span>' for r in rest)
    return f'<span class="nobr">{g}</span>'


def long_token(tok):
    if HEX.fullmatch(tok):
        return "<wbr>".join(tok[k:k + 8] for k in range(0, len(tok), 8))
    url = re.match(r"[a-z][a-z0-9+.-]*://[^/]+", tok)
    if url:   # the scheme and host of a URL (tcp://0.0.0.0:5557 too) stay whole
        return tok if url.end() == len(tok) else url.group(0) + long_token(tok[url.end():])
    if re.fullmatch(r"\d+(?:\.\d+){3}(?::\d+)?", tok):   # an IPv4 address and its port stay whole
        return tok
    tok = CAMEL.sub("\0", tok)
    if re.search(r"[/_:.]", tok):
        # Never after a leading /, : or _ (`/mnt/3fs`, `:11967-11972`, `_failed_items_total`), which would
        # stand alone at a line end.
        tok = tok[0] + BREAK_AFTER.sub("\\1\0", tok[1:]) if tok[0] in "/:_" else BREAK_AFTER.sub("\\1\0", tok)
    return tok.replace("\0", "<wbr>")


# A code location in running text: `src/x/File.cc:12-20`, `File.cc:12`, and the `, :30` that may follow.
CITE_TOKEN = re.compile(rf"(?<![\w/.+-])(?:[\w.+-]+/)*[\w+-]+(?:\.[\w+-]+)*\.(?:{EXT}):\d+(?:-\d+)?(?:,\s*:\d+(?:-\d+)?)*")
PAREN = re.compile(r"\([^()<>]*\)")
HANGUL = re.compile(r"[가-힣]")


def small_cites(body):
    """Set code locations in parentheses small (span.cite), so that a sentence reads through them: the
    whole parenthesis when it holds no Hangul, else each location in it. Listings keep theirs."""
    def paren(m):
        g = m.group(0)
        if not CITE_TOKEN.search(g):
            return g
        if not HANGUL.search(g):
            return f'<span class="cite">{g}</span>'
        return CITE_TOKEN.sub(r'<span class="cite">\g<0></span>', g)
    out, incode = [], False
    for part in re.split(r"(<pre[\s\S]*?</pre>|<[^>]+>)", body):
        if part.startswith("<"):
            incode = re.match(r"<code[\s>]", part) is not None or (incode and part != "</code>")
        out.append(part if not part or part.startswith("<") or incode else PAREN.sub(paren, part))
    return "".join(out)


# A space between two inline elements (`a` `b`, two .nobr words). Paged.js skips a text node that
# holds only white space when it rebuilds a block that continues from the page before, so such a
# space goes into a span of its own.
INLINE = r"(?:span|code|strong|em|a|b|i|sup|sub)"
INLINE_GAP = re.compile(rf"(</{INLINE}>)([ \t]+)(?=<(?:{INLINE}[\s>]|wbr>))")

LAST_WORDS = re.compile("(?:(?<=[\\s>\u2060])([가-힣]{1,6}) )?(?<=[\\s>\u2060])([가-힣]{2,6}[.?!]?[\"”’)]?)(?=</p>)")


NUM_HANGUL = re.compile(r"(?<![\w.])\d[\d,.]*[가-힣]{1,4}")


def pieces(text):
    """The tags and text runs of `text`, each with its offset."""
    k = 0
    for s in re.split(r"(<[^>]+>)", text):
        yield k, s
        k += len(s)


def depth(text, k):
    """Whether offset k of `text` lies inside a <span> opened in `text` itself (a .nobr from NOBR)."""
    head = text[:k]
    return head.count("<span") > head.count("</span>")


def add_breaks(body):
    """Let long paths and identifiers wrap (<wbr>) and keep flags and dates whole, in text outside <pre> and tags."""
    out = []
    for part in re.split(r"(<pre[\s\S]*?</pre>|<[^>]+>)", body):
        if not part or part.startswith("<"):
            out.append(part)
            continue
        # A parenthesis right after inline code may start the next line: `kMaxSliceSize`(16,777,200바이트).
        if part.startswith("(") and out and out[-1] == "</code>":
            out.append("<wbr>")
        # A particle stays with the inline code before it (`metadata_version`이다): a word joiner.
        if HANGUL.match(part) and out and out[-1] == "</code>":
            out.append("\u2060")
        # A particle stays with the closing parenthesis before it: (샤드가 다른 멤버 포함)와.
        part = re.sub(r"\)(?=[가-힣])", ")\u2060", part)
        if len(part) > 16:   # a short call such as LOG(FATAL) stays whole
            part = CALL_PAREN.sub("(<wbr>", part)
        part = re.sub(r"(?<=\w)@(?=\w)", "<wbr>@", part)   # a NIC path breaks before its @: 10.0.0.2:12345@mlx5_1
        part = LONG_TOKEN.sub(lambda m: long_token(m.group(0)), part)
        part = NOBR.sub(nobr, part)
        # A number keeps the Hangul right after it (31밀리초, 2.1의), and a .nobr span the particle
        # right after it (6.2절의). Spans, not U+2060, so that a search for "6.2절" still finds it.
        part = "".join(s if s.startswith("<") or depth(part, k) else NUM_HANGUL.sub(r'<span class="nobr">\g<0></span>', s)
                       for k, s in pieces(part))
        part = re.sub(r'(<span class="nobr">[^<]*)</span>([가-힣]{1,2})(?![가-힣])', r"\1\2</span>", part)
        part = re.sub(r"&lt;[^&<>]{1,24}&gt;", lambda m: f'<span class="nobr">{m.group(0)}</span>', part)
        out.append(part)
    return "".join(out)


URL = re.compile(r"https?://[^\s<>\"]*[^\s<>\".,;:)]")


def ref_list(block):
    """The entries ([n] ...) of a reference list: ragged right (a long URL would stretch a justified
    line) and every URL set as code, as most chapters already write them."""
    block = re.sub(r"<p>(?=\[\d+\])", '<p class="ref">', block)
    return "".join(part if part.startswith("<") else URL.sub(r"<code>\g<0></code>", part)
                   for part in re.split(r"(<code>[\s\S]*?</code>|<[^>]+>)", block))


def dense(kind, name):
    """A settings appendix: tables of five or six columns, typeset small (book.css section.dense)."""
    return kind == "app" and any(k in name for k in ("parameters", "settings", "config"))


SHORT_CODE, SHORT_CODE_DENSE = 24, 20


def short_cell_code(body, limit=SHORT_CODE):
    """Inline code of at most `limit` characters in a table cell never breaks (no <wbr>, and not after a
    hyphen either): Chrome sizes a column by its narrowest break, so `ibv_<wbr>reg_<wbr>mr` or
    `mooncake-store/` would make a narrow first column."""
    def code(m):
        if len(html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))) > limit:
            return m.group(0)
        return f'<code class="nobr">{m.group(1).replace("<wbr>", "")}</code>'
    return re.sub(r"<t([dh])\b([^>]*)>([\s\S]*?)</t\1>",
                  lambda c: re.sub(r"<code>([\s\S]*?)</code>", code, c.group(0)), body)


def convert(kind, name, text, puml_names, toc, slug):
    # Figures first, so markdown does not touch them.
    i = 0

    def puml(m):
        nonlocal i
        src = m.group(1)
        cap = re.search(r"^' (그림 [0-9A-Z]+\.\d+ .+)$", src, re.M)
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
    # Table captions: a `표 N.M 제목` paragraph right above a table (tools/check_book.py checks the numbers).
    body = re.sub(r"<p>(표 (?:\d{1,2}|[A-Z])\.\d{1,3}) (.*?)</p>\s*<table>",
                  r'<p class="tcap"><span class="tnum">\1</span>\2</p>\n<table>', body)
    if "references" in name:   # a references appendix (section.refs) is one reference list
        body = ref_list(body)
    else:
        body = re.sub(r"(<h2>[^<]*참고 문헌</h2>)([\s\S]*?)(?=<h[12][\s>]|\Z)", lambda m: m.group(1) + ref_list(m.group(2)), body)

    body = add_breaks(small_cites(body))
    body = short_cell_code(body, SHORT_CODE_DENSE if dense(kind, name) else SHORT_CODE)
    # The last two words of a paragraph each stay whole, so that the last line never starts inside a
    # word (는다.).
    body = LAST_WORDS.sub(lambda m: "".join(f'<span class="nobr">{w}</span>{sp}' for w, sp in
                                            ((m.group(1), " "), (m.group(2), "")) if w), body)
    body = INLINE_GAP.sub(r"\1<span>\2</span>", body)

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


INDEX_GROUP = re.compile(r"<h3>[^<]*</h3>\s*<ul>[\s\S]*?</ul>\s*")


def index_columns(body):
    """Set each run of index groups (a letter heading and its list) as one two-column block, so that
    the groups follow each other down the columns. A group of at most six entries stays in one column."""
    def group(m):
        short = " short" if m.group(0).count("<li") <= 6 else ""
        return f'<div class="ig{short}">{m.group(0)}</div>'
    return re.sub(rf"(?:{INDEX_GROUP.pattern})+",
                  lambda m: f'<div class="index-cols">{INDEX_GROUP.sub(group, m.group(0))}</div>\n', body)


def number_blocks(content):
    """Give every p, h2-h4, figure, pre, list, table and box a data-n number, every list item a
    data-li number and every body row its row number in the table (data-r), so that layout fixes
    can target one; mark tables of at most three body rows (data-short)."""
    n = li = 0

    def tag(m):
        nonlocal n
        n += 1
        return f'<{m.group(1)} data-n="{n}"{m.group(2)}'

    def item(m):
        nonlocal li
        li += 1
        return f'<li data-li="{li}"{m.group(1)}'

    def rows(m):
        r = 0

        def row(_):
            nonlocal r
            r += 1
            return f'<tr data-r="{r}"'
        return re.sub(r"<tr(?=[\s>])", row, m.group(0))
    content = re.sub(r"<(p|h2|h3|h4|figure|pre|ul|ol|table|blockquote)([\s>])", tag, content)
    content = re.sub(r"<li([\s>])", item, content)
    content = re.sub(r"<tbody>[\s\S]*?</tbody>", rows, content)
    # A table of at most three body rows would leave one row alone on a page if it broke: data-short
    # keeps it whole (book.css).
    return re.sub(r"<table [\s\S]*?</table>",
                  lambda m: m.group(0) if 'data-r="4"' in m.group(0) else m.group(0).replace(">", " data-short>", 1),
                  content)


def split_listings(content, cuts):
    """Cut listing n into one listing per page at the line numbers cuts[n] (counted over the whole listing).

    Paged.js 0.4.3 loses the line at the break when it splits a pre itself, so listings never
    break inside. Part k of listing n is numbered n with k "b"s and carries data-l, the number of
    its first line, so that the page checks can name a cut by its line in the whole listing."""
    for n, at in cuts.items():
        m = re.search(rf'<div class="hl"><pre data-n="{n}"([^>]*)>([\s\S]*?)<code>([\s\S]*?)</code></pre></div>', content)
        if not m:
            continue
        lines = re.findall(r'<div class="ln">[\s\S]*?</div>', m.group(3))
        bounds = [0] + sorted(c for c in set(at) if 0 < c < len(lines)) + [len(lines)]
        if len(bounds) == 2:
            continue
        parts = []
        for k in range(len(bounds) - 1):
            cls = " ".join(c for c, on in (("cont-prev", k > 0), ("cont-next", k < len(bounds) - 2)) if on)
            parts.append(f'<div class="hl"><pre data-n="{n}{"b" * k}" data-l="{bounds[k]}" class="{cls}"{m.group(1)}>'
                         f'{m.group(2) if k == 0 else ""}<code>{"".join(lines[bounds[k]:bounds[k + 1]])}</code></pre></div>')
        content = content[:m.start()] + "".join(parts) + content[m.end():]
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

    moves: {figure number: [numbers of the following blocks that fit before the page end]}.
    Only the leading run of blocks that really follow the figure, with nothing between, moves; a
    listing cut into parts ends the run. A figure in the list goes along with the moving one and
    stays right after it, and may then move on its own past the blocks after it (figures move in
    reading order). The figure records the blocks and figures it went past (data-moved)."""
    for fig, blocks in sorted(moves.items(), key=lambda kv: int(kv[0])):
        m = re.search(rf'\n?<figure data-n="{fig}"[\s\S]*?</figure>\n?', content)
        if not m:
            continue
        end, moved, passed, figs = m.end(), [], [], [m.group(0)]
        for n in blocks:
            f = re.match(rf'\s*<figure data-n="{n}"[\s\S]*?</figure>\n?', content[end:])
            if f:
                figs.append(f.group(0))
                end += f.end()
                moved.append(n)
                continue
            b = re.match(rf'\s*(<(p|ul|ol|table|blockquote|h3|h4)|<div class="hl"><pre) data-n="{n}"[\s>][^>]*', content[end:])
            if not b or "cont-next" in b.group(0):
                break
            start, end = end, block_end(content, end)
            passed.append(content[start:end])
            moved.append(n)
        if passed:
            figs[0] = figs[0].replace(f'data-n="{fig}"', f'data-n="{fig}" data-moved="{" ".join(moved)}"', 1)
            content = content[:m.start()] + "".join(passed) + "".join(figs) + content[end:]
    return content


TEXT_W = "143mm"  # text block width of book.css (183 mm page, 22 + 18 mm margins)

# Additions to Paged.js 0.4.3 for the tables it splits. Before layout, each table is laid out
# whole at the text width and its column widths are fixed (book.css table[data-cols]); Paged.js
# would lay out each part on its own, so the columns would move from page to page. During
# layout, the part that continues a table on a new page gets a copy of the head row; the copy
# goes in before the page is checked for overflow, so that its height counts.
PAGED_JS = """
async function fixTableColumns() {
  const st = document.createElement('style');
  st.textContent = 'body { width: %(w)s !important; }';
  document.head.appendChild(st);
  document.body.offsetHeight;
  await document.fonts.ready;
  const widths = [...document.querySelectorAll('table')].map((t) => {
    const row = t.tHead && t.tHead.rows[0];
    const total = t.getBoundingClientRect().width;
    return row && total ? [t, [...row.cells].map((c) => c.getBoundingClientRect().width / total * 100)] : null;
  }).filter(Boolean);
  // Attributes, not inline styles: Paged.js takes an element with a style attribute for one that
  // is not displayed, and then passes a heading's break-after: avoid on past the table.
  for (const [t, w] of widths) {
    t.setAttribute('data-cols', '');
    [...t.tHead.rows[0].cells].forEach((c, k) => c.setAttribute('width', (Math.floor(w[k] * 1000) / 1000) + '%%'));
  }
  st.remove();
}
class RepeatTableHead extends Paged.Handler {
  constructor(chunker, polisher, caller) { super(chunker, polisher, caller); this.tables = []; }
  afterPageLayout(pageElement, page, breakToken) {
    // The tables that the break is inside of (not a table that starts the next page).
    this.tables = [];
    const node = breakToken && breakToken.node;
    for (let t = node && node.parentElement && node.parentElement.closest('table'); t;
         t = t.parentElement && t.parentElement.closest('table')) this.tables.push(t);
  }
  layout(rendered) {
    for (const src of this.tables) {
      const t = rendered.querySelector(`table[data-ref="${src.dataset.ref}"]`);
      if (t && !t.tHead && src.tHead) t.insertBefore(src.tHead.cloneNode(true), t.firstChild);
    }
  }
}
Paged.registerHandlers(RepeatTableHead);
""" % {"w": TEXT_W}


def build_html(jar, print_mode, fixes="", moves=None, cuts=None, breaks=()):
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
        if name == "index.md":
            body = index_columns(body)
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
        # Settings appendices (kernel parameters, config keys) use the same small type; a chapter about
        # configuration does not.
        extra += " dense" if dense(kind, name) else ""
        # A references appendix is a long numbered list of citations: smaller type.
        extra += " refs" if "references" in name else ""
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
        svg = with_version((BOOK / "cover.svg").read_text(encoding="utf-8"))
        svg = re.sub(r'(<svg[^>]*?) width="\d+" height="\d+"', r'\1 width="183mm" height="235mm"', svg, count=1)
        cover = f'<section id="cover" class="cover">{svg}</section>'

    content = number_blocks(f"{cover}{title_page}{toc_html}{''.join(sections)}")
    content = move_figures(split_listings(content, cuts or {}), moves or {})
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
           f"<script>window.__fixBreaks = {json.dumps(list(breaks))};</script>"
           "<script>window.PagedConfig = { auto: true, before: () => fixTableColumns(), "
           "after: (flow) => { window.__pagedDone = flow.total; } };</script>"
           '<script src="../tools/vendor/pagedjs/paged.polyfill.js"></script>'
           f"<script>{PAGED_JS}</script>"
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


# A listing cut whose two parts landed on one page (the page checks report it, and the next pass
# takes the cut back): until then the parts are drawn as one box. This only shortens the page.
JOIN_CUTS = """(() => {
  let n = 0;
  document.querySelectorAll('.pagedjs_page_content pre.cont-next').forEach((pre) => {
    const next = document.querySelector(`.pagedjs_page_content pre[data-n="${pre.dataset.n}b"]`);
    if (!next || pre.closest('.pagedjs_page') !== next.closest('.pagedjs_page')) return;
    Object.assign(pre.style, {marginBottom: '0', paddingBottom: '0', borderBottomWidth: '0'});
    Object.assign(next.style, {marginTop: '-1px', paddingTop: '0', borderTopWidth: '0'});
    n++;
  });
  return n;
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
        info["joined"] = chrome.eval(JOIN_CUTS)
        chrome.pdf(pdf_path)
        warnings = [m for kind, m in chrome.console if kind in ("warning", "error")]
    finally:
        chrome.close()
    lines = [f"{i['page']}\t{i['kind']}\t{i['what']}" for i in issues] + [f"-\tconsole\t{w}" for w in warnings]
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return info, issues, warnings, time.time() - start


# Five passes left listing cuts mid-page and one-row table parts in the 490-page Mooncake book;
# eight let them settle.
PASSES = 12
SHORT_TABLE = 6  # body rows: a table this short that would leave one row alone on a page is kept whole


def fixes_for(issues):
    """Fixes for what the page checks found: a heading alone at the bottom of a page moves to the
    next page, as does a heading whose short lead line is all that precedes its listing or figure
    there (a listing is cut instead when three lines of it fit), a paragraph or list item with one
    line on a page stays whole when that costs at most five lines of space (as does a block that
    runs past the page bottom), a figure that left a page mostly empty shrinks to fit there when it
    is at most 5% too tall or else floats below the blocks that fit there, a listing that did the
    same is cut where the page ends, a table that leaves one body row alone on a page stays whole
    when short or else moves a row, a table wider than the text lets its identifiers break anywhere,
    a paragraph with a line of stretched word spaces spreads the space between characters instead,
    and a part opener that runs onto a second page loses most of its top space.

    Returns (CSS rules as (selector, property, value, check that asked for it), layout changes).
    A layout change adds or removes a listing cut ("cut", listing, line, line it replaces or None;
    "uncut", listing, line), sets or narrows a figure move ("move", figure, blocks; "unmove",
    figure, blocks kept, veto) or drops a forced page break ("drop", selector, veto)."""
    rules, changes = [], []
    for i in issues:
        if i["kind"] == "part-overflow" and i.get("sid"):
            # Paged.js rewrites #id to [data-id=...], so the class keeps this above section.part.
            rules.append((f'section.part#{i["sid"]}', "padding-top", "16mm", "part"))
        if i.get("paras"):
            changes.append(("move", i["fig"], tuple(i["paras"])))
        if "keep" in i:
            changes.append(("unmove", i["fig"], tuple(i["keep"]), i.get("veto", False)))
        if i.get("shrink"):
            rules.append((f'figure.fig[data-n="{i["shrink"]}"] img', "max-height", f'{i["maxh"]}mm', "shrink"))
        if i.get("split"):
            changes.append(("cut", i["split"], i["at"], i.get("replace")))
        if i.get("uncut"):
            changes.append(("uncut", i["uncut"], i["at"]))
        if i.get("drop"):
            changes.append(("drop", i["drop"], i.get("veto", False)))
        if i["kind"] == "table-split":
            if i["total"] <= SHORT_TABLE:
                rules.append((f'table[data-n="{i["n"]}"]', "break-inside", "avoid", "table"))
                if i.get("lead") and i["lead"] != i["n"]:   # its lead goes to the next page with it
                    rules.append((f'[data-n="{i["lead"]}"]', "break-before", "page", "table"))
            elif i.get("row"):
                rules.append((f'table[data-n="{i["n"]}"] tr[data-r="{i["row"]}"]', "break-before", "page", "row"))
            else:
                rules.append((f'[data-n="{i["lead"]}"]', "break-before", "page", "table"))
            continue
        sel = i.get("sel") or (f'[data-n="{i["n"]}"]' if i.get("n") else None)
        if not sel:
            continue
        if i["kind"] == "heading-at-bottom":
            rules.append((sel, "break-before", "page", "heading"))
        elif i["kind"] == "heading-lead-at-bottom" and not i.get("split"):
            rules.append((sel, "break-before", "page", "lead"))
        elif i["kind"] == "wide-gaps":
            rules.append((sel, "text-justify", "inter-character", "spacing"))
        elif i["kind"] == "overflow-x" and i["what"].startswith("table"):
            rules.append((f'table[data-n="{i["n"]}"] code', "overflow-wrap", "anywhere", "overflow"))
        elif i["kind"] == "overflow-y" and i.get("head"):
            rules.append((f'[data-n="{i["head"]}"]', "break-before", "page", "overflow"))
        elif i["kind"] in ("orphan", "overflow-y") or (i["kind"] == "widow" and i.get("before", 99) <= 5):
            rules.append((sel, "break-inside", "avoid", i["kind"]))
    return rules, changes


class Fixes:
    """What the next pass applies: CSS rules by (selector, property), listing cuts and figure moves.

    A change replaces the earlier one for the same target: a rule for the same selector and
    property, a cut that a part of a listing moves (a part that continues a listing from the page
    before takes more lines there), and a figure's new move. Cuts, moves and forced page breaks
    that a later layout no longer needs are taken back; a move or break taken back because it
    left a page mostly empty is not made again (vetoed)."""

    def __init__(self):
        self.rules, self.cuts, self.moves, self.vetoed = {}, {}, {}, set()

    def state(self):
        return repr((sorted(self.rules.items()), sorted((n, sorted(v)) for n, v in self.cuts.items()),
                     sorted(self.moves.items())))

    def css(self):
        return "\n".join(f"{sel} {{ {prop}: {val}; }}" for (sel, prop), (val, _) in self.rules.items())

    def breaks(self):
        """The page breaks that fixes forced, for the page checks to take back when no longer needed."""
        return [{"sel": sel, "why": why} for (sel, prop), (val, why) in self.rules.items()
                if prop == "break-before" and why in ("heading", "lead", "table", "row")]

    def apply(self, rules, changes):
        for sel, prop, val, why in rules:
            if ("rule", sel) not in self.vetoed:
                self.rules[(sel, prop)] = (val, why)
        for c in changes:
            if c[0] == "cut":
                _, n, at, old = c
                lines = self.cuts.setdefault(n, set())
                lines.discard(old)
                lines.add(at)
            elif c[0] == "uncut":
                self.cuts.get(c[1], set()).discard(c[2])
            elif c[0] == "move" and c[1] not in self.vetoed:
                self.moves[c[1]] = c[2]
            elif c[0] == "unmove":
                _, fig, keep, veto = c
                if keep:
                    self.moves[fig] = keep
                else:
                    self.moves.pop(fig, None)
                if veto:
                    self.vetoed.add(fig)
            elif c[0] == "drop":
                self.rules.pop((c[1], "break-before"), None)
                if c[2]:
                    self.vetoed.add(("rule", c[1]))
        for n in [n for n, lines in self.cuts.items() if not lines]:
            del self.cuts[n]


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

    # Lay out, fix what the page checks found, and lay out again (at most PASSES passes). Each pass
    # also takes back the cuts, moves and forced breaks that its layout no longer needs, so the
    # last layout keeps only the ones that still do their job.
    fixes = Fixes()
    for attempt in range(PASSES):
        doc, toc = build_html(args.jar, args.print_mode, fixes.css(), fixes.moves, fixes.cuts, fixes.breaks())
        html_path.write_text(doc, encoding="utf-8")
        info, issues, warnings, secs = layout(html_path, pdf, BUILD / f"{stem}-qa.txt")
        rules, changes = fixes_for(issues)
        before = fixes.state()
        kinds = {"rule": sum(fixes.rules.get((sel, prop), (None,))[0] != val for sel, prop, val, _ in rules)}
        for c in changes:
            kinds[c[0]] = kinds.get(c[0], 0) + 1
        fixes.apply(rules, changes)
        if fixes.state() == before:
            break
        if attempt == PASSES - 1:
            print(f"pass {attempt + 1}: changes left unapplied: {kinds}", file=sys.stderr)
            break
        print(f"pass {attempt + 1}: {kinds}", file=sys.stderr)
    if args.print_mode:
        set_boxes(pdf, 3.0)
    kinds = {}
    for i in issues:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(f"{pdf} ({info['pages']} pages, layout {secs:.0f} s); TOC entries without a page: {len(info['missing'])}"
          + (f"; listing cuts drawn as one box: {info['joined']}" if info["joined"] else ""))
    print("page checks:", ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "no issues",
          f"; console warnings: {len(warnings)}; details in {BUILD / (stem + '-qa.txt')}")


if __name__ == "__main__":
    main()
