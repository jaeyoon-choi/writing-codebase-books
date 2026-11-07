#!/usr/bin/env python3
"""Check book chapters against the pinned commit of the source repository and the writing rules.

Checks, per file:
  - every `path:line` citation names a file at BASE and a line inside it
  - every listing whose first line is `// path:line` (or `# path:line`)
    starts at that line and then follows the source in order
  - no em dash, no Mermaid, no hard-wrapped paragraphs
  - headings are noun phrases (no sentence or question endings)      [lang = "ko"]
  - paragraph sentences end with a predicate (heuristic: `다.` and friends)  [lang = "ko"]
  - in the concept sections of a chapter (kind "ch" in [layout] order), no paragraph or list item has more than
    MAX_CITES_PER_PARA citations (tables and `**불변식` paragraphs are exempt); the summary prints
    concept-section citations per 1,000 characters (cite/1k)
  - in a chapter (chNN-*.md) or appendix (appendix-x-*.md), every table has a caption line
    `표 N.M 제목` (`표 X.M` in appendix X) right above it, numbered 1, 2, ... in order; the
    title is a noun phrase                                          [lang = "ko" for the title]
  - the particle after `표 N.M` or `그림 N.M` agrees with how the number is read
    (`표 4.1은`, `표 4.2는`)                                          [lang = "ko"]
  - a bare citation `:N` points inside the file named last before it (on the same line, else
    earlier in the file, as in a table under a paragraph that names the file)
  - a figure image line `![그림 N.M ...](figures/fig-A-B-name...)` uses the file of its own
    number (A.B = N.M), so that a renumbered figure does not keep an old file name
  - prose does not name a PlantUML box by its alias (`"label" as ALIAS`) when the figure
    shows only the label
With several files, also checks that every `N.M절` reference names a
numbered heading and every `표 N.M` reference names a table caption
somewhere in the set. References right after the companion book's name
([book] companion, e.g. `본편 7.3절` in a summary edition) are not checked.

With --cites-since REV (a commit of the book's own repository), also lists the
citations that the given files had at REV and whose lines the citations of the
same source file no longer cover: "gone" when none overlaps, "narrowed" when
some do. The list is a report for the reviewer of a rewrite and does not count
as problems, because a citation may go away with its claim.

Sources are read with `git show BASE:path`, so the working tree of the
source checkout does not matter. The repository, commit and citation file
extensions come from book.toml ([source]); a citation path must start with a
top-level entry of the repository at that commit.
"""
import argparse
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconf  # noqa: E402

REPO = str(Path(bookconf.source()["repo"]).expanduser())
BASE = bookconf.source()["commit"]
KOREAN = bookconf.book().get("lang", "ko") == "ko"
EXTS = bookconf.source().get("extensions", ["c", "cc", "cpp", "h", "hpp", "rs", "go", "py", "md", "toml", "txt"])
# A summary edition names its full book (e.g. "본편"); `본편 7.3절` and `본편 표 7.3` point there, not here.
COMPANION = bookconf.book().get("companion")


def own_ref(text, start):
    """Whether the reference at start belongs to this book, not to the companion book named just before it."""
    return not (COMPANION and re.search(re.escape(COMPANION) + r"의? $", text[:start]))


def _top_level():
    """Top-level directories, and top-level file names without extension, at the pinned commit."""
    dirs, files = [], []
    out = subprocess.run(["git", "-C", REPO, "ls-tree", BASE], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        meta, name = line.split("\t", 1)
        if name.startswith("."):
            continue
        if meta.split()[1] == "tree":
            dirs.append(re.escape(name))
        elif "." in name:
            files.append(re.escape(name.rsplit(".", 1)[0]))
    return dirs, files


_DIRS, _FILES = _top_level()
PATH_RE = (r"(?:(?:" + "|".join(_DIRS or ["src"]) + r")/[A-Za-z0-9_./+-]+"
           + (r"|" + "|".join(_FILES) if _FILES else "") + r")"
           r"\.(?:" + "|".join(re.escape(e) for e in EXTS) + r")")
ANCHOR = re.compile(r"(?<![\w/])(" + PATH_RE + r"):(\d+)(?:-(\d+))?")
# Short form used after a full path in the same paragraph: `Foo.cc:12`.
SHORT = re.compile(r"(?<![\w/.+-])([A-Za-z0-9_+-]+\.(?:" + "|".join(re.escape(e) for e in EXTS) + r")):(\d+)(?:-(\d+))?")
# Bare form after a named file earlier on the same line: `:3931`, `:12-20`.
BARE = re.compile(r"`:(\d+)(?:-(\d+))?`")
FIG_FILE = re.compile(r"^fig-([0-9a-z]+)-(\d+)-")
FIG_NUM = re.compile(r"^그림 ([0-9A-Z]+)\.(\d+) ")
PUML_ALIAS = re.compile(r'"([^"]+)"\s+as\s+(\w+)')
FENCE_OPEN = re.compile(r"^```(\w[\w+-]*)?\s*$")
ORIGIN = re.compile(r"^\s*(?://|#|--)\s*(" + PATH_RE + r"):(\d+)\s*$")
HANGUL = re.compile(r"[가-힣]")
# A `##` section is a code section when its title starts with one of these
# (after the N.M number); every other `##` section of a chapter is a concept section.
CODE_SECTION = re.compile(r"^##\s+(?:\d{1,2}\.\d{1,2}\s+)?(?:코드|Code\b)")
MAX_CITES_PER_PARA = 3
INVARIANT = "**불변식"
ELISION = re.compile(r"^\s*(//\s*\.\.\.|#\s*\.\.\.|\.\.\.|/\*\s*\.\.\.\s*\*/)\s*$")
XREF = re.compile(r"(\d{1,2})\.(\d{1,2})절")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
FIG_ALT = re.compile(r"^그림 (?:\d+|[A-Z])\.\d+ \S")
TABLE_CAP = re.compile(r"^표 ((?:\d{1,2}|[A-Z])\.\d{1,3}) (\S.*)$")
TABLE_REF = re.compile(r"표 ((?:\d{1,2}|[A-Z])\.\d{1,3})(?!\d)")
NUM_PARTICLE = re.compile(r"((?:표|그림) (?:\d{1,2}|[A-Z])\.(\d{1,3}))([가-힣]+)")
# Final consonant of the last digit as read in Korean (일, 이, 삼, ...): "" none, "l" ㄹ, "c" another one.
DIGIT_FINAL = {"0": "c", "1": "l", "2": "", "3": "c", "4": "", "5": "", "6": "c", "7": "l", "8": "l", "9": ""}


def particle_mismatch(final, word):
    """True when the particle at the start of word does not fit a number whose reading ends in final."""
    for after_consonant, after_vowel in (("은", "는"), ("을", "를"), ("과", "와"), ("이", "가")):
        if word.startswith(after_consonant) and not final and after_consonant != "이":
            return True
        if word.startswith(after_vowel) and final:
            return True
    if word == "이" and not final:   # the subject particle; 이다, 이므로 after a vowel are the copula
        return True
    if word.startswith("으로"):
        return final != "c"
    if word.startswith("로"):
        return final == "c"
    return False
NUM_HEADING = re.compile(r"^#{2,4}\s+(\d{1,2})\.(\d{1,2})\b")
BAD_HEADING_END = re.compile(r"(다|다\.|니다|세요|어요|아요|까|\?|\.)$")
SENT_OK_END = re.compile(r"(다|까|요|라|자|죠|오)\.$|(가|까|나|지)\?$|[:)\]`|]$|\.\)$|다:$|\.\"$|다\"$|다\([^)]*\)\.$|\.\*\*$|다\.\*$|다(\[\d+\])+\.$")
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s")

PROSE_CHARS_PER_PAGE = 1300
CODE_LINES_PER_PAGE = 45
TABLE_ROWS_PER_PAGE = 30
FIGURE_PAGES = 0.4


@lru_cache(maxsize=None)
def source_lines(path: str):
    res = subprocess.run(["git", "-C", REPO, "show", f"{BASE}:{path}"], capture_output=True)
    if res.returncode != 0:
        return None
    return res.stdout.decode("utf-8", errors="replace").splitlines()


@lru_cache(maxsize=None)
def basename_index():
    res = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", BASE], capture_output=True, text=True,
                         check=True)
    idx = {}
    for p in res.stdout.splitlines():
        idx.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    return idx


def norm(line: str) -> str:
    line = line.rstrip()
    if line.endswith("\\"):
        line = line[:-1]
    return re.sub(r"\s+", " ", line).strip()


def strip_added_comment(line: str) -> str:
    for marker in ("//", "#"):
        idx = line.find(marker)
        if idx >= 0 and HANGUL.search(line[idx:]):
            return line[:idx].rstrip()
    return line


def check_range(path, start, end, where, problems):
    lines = source_lines(path)
    if lines is None:
        problems.append(f"{where}: no such file at base: {path}")
        return
    s = int(start)
    e = int(end) if end else s
    if s < 1 or e > len(lines) or e < s:
        problems.append(f"{where}: {path}:{start}{'-' + end if end else ''} out of range ({len(lines)} lines)")


def check_listing(block, where, problems):
    m = ORIGIN.match(block[0])
    if not m:
        return False
    path, start = m.group(1), int(m.group(2))
    src = source_lines(path)
    if src is None:
        problems.append(f"{where}: listing source missing at base: {path}")
        return True
    pos = start - 1
    first = True
    elided = False
    for ln in block[1:]:
        if not ln.strip() or ELISION.match(ln):
            if ELISION.match(ln):
                elided = True
            continue
        stripped = ln.strip()
        if HANGUL.search(ln) and (stripped.startswith("//") or stripped.startswith("#")):
            continue
        needle = norm(strip_added_comment(ln))
        if not needle:
            continue
        if first:
            if pos >= len(src) or norm(src[pos]) != needle:
                problems.append(f"{where}: listing {path}:{start} does not start at that line "
                                f"(source has: {norm(src[pos])[:60] if pos < len(src) else 'EOF'!r})")
                return True
            pos += 1
            first = False
            continue
        found = None
        for j in range(pos, len(src)):
            if norm(src[j]) == needle:
                found = j
                break
        if found is None:
            problems.append(f"{where}: listing {path}:{start}: line not found in order: {needle[:70]}")
            return True
        skipped = [norm(x) for x in src[pos:found]]
        if not elided and any(x and not x.startswith(("//", "/*", "*", "#")) for x in skipped):
            problems.append(f"{where}: listing {path}:{start}: source lines {pos + 1}-{found} skipped without `// ...`")
        elided = False
        pos = found + 1
    return True


def is_chapter(name: str) -> bool:
    try:
        kinds = {n: k for k, n in bookconf.order()}
    except KeyError:
        kinds = {}
    return kinds.get(name, "ch" if name.startswith("ch") else "") == "ch"


def check_file(doc: Path, problems, headings, xrefs, stats, captions, table_refs):
    text = doc.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_fence = False
    fence_lang = None
    block = []
    block_start = 0
    prose_chars = code_lines = table_rows = figures = 0
    prev_para = False
    last_full_paths = []
    last_named = None   # the file that a bare `:N` on a later line refers to
    chapter = is_chapter(doc.name)
    # Tables of chapter N are numbered N.M, tables of appendix X are numbered X.M.
    cm = re.match(r"ch(\d+)-", doc.name)
    am = re.match(r"appendix-([a-z])-", doc.name)
    table_prefix = str(int(cm.group(1))) if cm else am.group(1).upper() if am else None
    tables = 0
    caption = None      # (number, line) of a caption line still waiting for its table
    in_table = False
    in_code_section = not chapter
    concept_chars = concept_cites = 0
    # PlantUML aliases of this file: prose that names a box by its alias points at nothing the reader sees.
    aliases = {}
    for blk in re.findall(r"```plantuml\n(.*?)```", text, re.S):
        for label, name in PUML_ALIAS.findall(blk):
            aliases[name] = label

    for i, raw in enumerate(lines, 1):
        where = f"{doc.name}:{i}"
        if "—" in raw:
            problems.append(f"{where}: em dash")
        if in_fence:
            if raw.strip().startswith("```"):
                in_fence = False
                if fence_lang == "plantuml":
                    figures += 1
                elif fence_lang == "mermaid":
                    problems.append(f"{doc.name}:{block_start}: mermaid diagram (use PlantUML)")
                else:
                    code_lines += len(block)
                    if block:
                        check_listing(block, f"{doc.name}:{block_start}", problems)
                block = []
            else:
                block.append(raw)
            prev_para = False
            continue
        m = FENCE_OPEN.match(raw.strip())
        if raw.strip().startswith("```"):
            in_fence = True
            fence_lang = (m.group(1) if m else "") or ""
            block = []
            block_start = i
            prev_para = False
            continue

        anchor_ms = list(ANCHOR.finditer(raw))
        anchors = [m.groups() for m in anchor_ms]
        # A top-level file such as README.md:30 matches both patterns; count it once.
        short_ms = [m for m in SHORT.finditer(raw)
                    if not any(a.start() <= m.start() < a.end() for a in anchor_ms)]
        shorts = [m.groups() for m in short_ms]
        named = []      # (position, path) of each citation that names its file, for the bare ones after it
        for m in anchor_ms:
            path, start, end = m.groups()
            check_range(path, start, end, where, problems)
            last_full_paths.append(path)
            named.append((m.start(), path))
        for m in short_ms:
            name, start, end = m.groups()
            cands = [p for p in last_full_paths if p.rsplit("/", 1)[-1] == name]
            if not cands:
                cands = basename_index().get(name, [])
            if cands:
                check_range(cands[-1], start, end, where, problems)
                named.append((m.start(), cands[-1]))
            else:
                problems.append(f"{where}: short citation with unknown file: {name}:{start}")
        named.sort()
        for m in BARE.finditer(raw):
            before = [p for pos, p in named if pos < m.start()] or ([last_named] if last_named else [])
            if before:
                check_range(before[-1], m.group(1), m.group(2), where, problems)
            else:
                problems.append(f"{where}: bare citation `:{m.group(1)}` with no named file before it")
        if named:
            last_named = named[-1][1]
        for tok in re.findall(r"`([A-Za-z_]\w*)`", raw):
            label = aliases.get(tok)
            if label is not None and tok not in re.sub(r"\\n|\s", "", label):
                problems.append(f"{where}: `{tok}` is a PlantUML alias; name the box by its label: "
                                f"{label.replace(chr(92) + 'n', ' ')}")
        for m in XREF.finditer(raw):
            if own_ref(raw, m.start()):
                xrefs.append((int(m.group(1)), int(m.group(2)), where))
        if KOREAN:
            for m in NUM_PARTICLE.finditer(raw):
                if particle_mismatch(DIGIT_FINAL[m.group(2)[-1]], m.group(3)):
                    problems.append(f"{where}: particle does not fit the number: {m.group(1)}{m.group(3)[:2]}")
        s = raw.strip()
        tm = TABLE_CAP.match(s)
        text = raw[tm.end(1):] if tm else raw
        for m in TABLE_REF.finditer(text):
            if own_ref(text, m.start()):
                table_refs.append((m.group(1), where))
        if s.startswith("|"):
            if not in_table and table_prefix:
                tables += 1
                expected = f"{table_prefix}.{tables}"
                if caption is None or caption[1] != i - 2 or lines[i - 2].strip():
                    problems.append(f"{where}: table without a caption line '표 {expected} 제목' "
                                    f"and one blank line above it")
                elif caption[0] != expected:
                    problems.append(f"{doc.name}:{caption[1]}: table caption 표 {caption[0]}, expected 표 {expected}")
                caption = None
            # Header cells are bold, and the embedded mono font has no bold Hangul, so Chrome emits Type 3 glyphs.
            if not in_table and any(HANGUL.search(c) for c in re.findall(r"`([^`]+)`", s)):
                problems.append(f"{where}: Hangul inside a code span in a table header (Type 3 font in the PDF)")
            in_table = True
        else:
            # Python-Markdown folds such a line into the table, and a `>` box there vanishes from the print.
            if in_table and s:
                problems.append(f"{where}: text directly after a table (add a blank line)")
            in_table = False
        if caption is not None and s and not s.startswith("|"):
            problems.append(f"{doc.name}:{caption[1]}: table caption is not followed by a table")
            caption = None
        if tm and table_prefix:
            captions.add(tm.group(1))
            if KOREAN and BAD_HEADING_END.search(tm.group(2)):
                problems.append(f"{where}: table caption looks like a sentence: {tm.group(2)}")
            caption = (tm.group(1), i)
            prev_para = False
            continue

        hm = HEADING.match(raw)
        if hm:
            if len(hm.group(1)) == 2:
                in_code_section = not chapter or bool(CODE_SECTION.match(raw))
            title = hm.group(2).strip()
            if KOREAN and BAD_HEADING_END.search(title) and not title.endswith("..."):
                problems.append(f"{where}: heading looks like a sentence or question: {title}")
            nm = NUM_HEADING.match(raw)
            if nm:
                headings.add((int(nm.group(1)), int(nm.group(2))))
            prev_para = False
            continue

        s = raw.strip()
        if not s:
            prev_para = False
            continue
        if s.startswith("|"):
            table_rows += 1
            prev_para = False
            continue
        is_quote = s.startswith(">")
        body = s.lstrip(">").strip() if is_quote else s
        im = IMAGE.match(s)
        if im:
            alt, target = im.groups()
            if not (doc.parent / target).is_file():
                problems.append(f"{where}: image file not found: {target}")
            if target.endswith(".drawio.svg"):
                figures += 1
                if not FIG_ALT.match(alt):
                    problems.append(f"{where}: figure alt text should start with '그림 N.M 제목': {alt}")
                fm, nm = FIG_FILE.match(target.rsplit("/", 1)[-1]), FIG_NUM.match(alt)
                if fm and nm and (fm.group(1), fm.group(2)) != (nm.group(1).lower(), nm.group(2)):
                    problems.append(f"{where}: figure {nm.group(1)}.{nm.group(2)} uses the file of figure "
                                    f"{fm.group(1)}.{fm.group(2)} ({target}); rename the file and its script")
            prev_para = False
            continue
        if body and not in_code_section and not s.startswith("<"):
            cites = len(anchors) + len(shorts)
            concept_chars += len(body)
            concept_cites += cites
            # An invariant must name the code that keeps it and the test that checks it.
            if cites > MAX_CITES_PER_PARA and not body.startswith(INVARIANT):
                problems.append(f"{where}: {cites} citations in one concept-section paragraph "
                                f"(max {MAX_CITES_PER_PARA}; move the rest to a code-section table)")
        if LIST_ITEM.match(raw) or s.startswith("<") or s.startswith("!["):
            prose_chars += len(body)
            prev_para = False
            continue
        if not body:
            prev_para = False
            continue
        prose_chars += len(body)
        # A paragraph line directly after another paragraph line is a hard wrap.
        if prev_para and not is_quote:
            problems.append(f"{where}: paragraph continues on a new line (hard wrap)")
        prev_para = not is_quote
        # Sentence ending heuristic for Korean prose lines.
        whole_bold = body.startswith("**") and body.endswith("**") and body.count("**") == 2
        if HANGUL.search(body) and not whole_bold:
            tail = body.rstrip()
            if KOREAN and HANGUL.search(tail[-6:]) and not SENT_OK_END.search(tail):
                problems.append(f"{where}: sentence may not end with a predicate: ...{tail[-25:]}")

    pages = (prose_chars / PROSE_CHARS_PER_PAGE + code_lines / CODE_LINES_PER_PAGE
             + table_rows / TABLE_ROWS_PER_PAGE + figures * FIGURE_PAGES)
    code_pages = code_lines / CODE_LINES_PER_PAGE
    density = concept_cites * 1000 / concept_chars if concept_chars else 0
    stats.append((doc.name, prose_chars, code_lines, table_rows, figures, pages,
                  (code_pages / pages * 100) if pages else 0, density))


def cited_ranges(text):
    """(path, start, end, line number, column) of each citation, resolving `Foo.cc:12` and `:12` as check_file does."""
    out, full_paths, last_named = [], [], None
    for i, raw in enumerate(text.splitlines(), 1):
        anchor_ms = list(ANCHOR.finditer(raw))
        named = []
        for m in anchor_ms:
            full_paths.append(m.group(1))
            named.append((m.start(), m.group(1), m.group(2), m.group(3)))
        for m in SHORT.finditer(raw):
            if any(a.start() <= m.start() < a.end() for a in anchor_ms):
                continue
            cands = [p for p in full_paths if p.rsplit("/", 1)[-1] == m.group(1)] or basename_index().get(m.group(1), [])
            if cands:
                named.append((m.start(), cands[-1], m.group(2), m.group(3)))
        named.sort()
        for col, path, s, e in named:
            out.append((path, int(s), int(e or s), i, col))
        for m in BARE.finditer(raw):
            before = [p for pos, p, _, _ in named if pos < m.start()] or ([last_named] if last_named else [])
            if before:
                out.append((before[-1], int(m.group(1)), int(m.group(2) or m.group(1)), i, m.start()))
        if named:
            last_named = named[-1][1]
    return out


def uncovered(s, e, ranges):
    """Whether some line of s..e lies outside every range."""
    for a, b in sorted(ranges):
        if a > s:
            return True
        s = max(s, b + 1)
        if s > e:
            return False
    return True


def cites_gone(files, rev, problems):
    """[(file, line, path, start, end, excerpt, overlapping ranges now)] cited at rev and not covered now.

    An empty last element means no citation of the same path overlaps the old range (gone);
    otherwise the old range was narrowed, as when a broad citation stayed only as a few lines.
    """
    now, old = {}, []
    for f in files:
        p = Path(f)
        if p.is_file():
            for path, s, e, _, _ in cited_ranges(p.read_text(encoding="utf-8")):
                now.setdefault(path, []).append((s, e))
        res = subprocess.run(["git", "show", f"{rev}:./{p.name}"], cwd=p.parent, capture_output=True, text=True)
        if res.returncode != 0:
            # A file added after rev has nothing to lose; any other failure is a bad rev or no repository.
            if "exists on disk, but not in" not in res.stderr and "does not exist in" not in res.stderr:
                problems.append(f"--cites-since {rev}: {res.stderr.strip()}")
                return []
            continue
        lines = res.stdout.splitlines()
        for path, s, e, i, col in cited_ranges(res.stdout):
            old.append((p.name, i, path, s, e, lines[i - 1][max(0, col - 60):col].lstrip()))
    gone, seen = [], set()
    for name, i, path, s, e, excerpt in old:
        if (path, s, e) in seen or not uncovered(s, e, now.get(path, [])):
            continue
        seen.add((path, s, e))
        gone.append((name, i, path, s, e, excerpt, sorted(r for r in set(now.get(path, [])) if r[0] <= e and s <= r[1])))
    return gone


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--xref", action="store_true", help="check N.M절 and 표 N.M references across the given files")
    ap.add_argument("--cites-since", metavar="REV",
                    help="list citations the files had at REV (a commit of the book's repository) and lost since")
    args = ap.parse_args(argv[1:])
    problems, headings, xrefs, stats = [], set(), [], []
    captions, table_refs = set(), []
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            problems.append(f"no such file: {f}")
            continue
        check_file(p, problems, headings, xrefs, stats, captions, table_refs)
    if args.xref:
        for a, b, where in xrefs:
            if (a, b) not in headings:
                problems.append(f"{where}: reference to {a}.{b}절 but no such numbered heading")
        for ref, where in table_refs:
            if ref not in captions:
                problems.append(f"{where}: reference to 표 {ref} but no such table caption")
    gone = cites_gone(args.files, args.cites_since, problems) if args.cites_since else []
    for p in problems:
        print(p)
    if args.cites_since:
        print()
        span = lambda a, b: f"{a}-{b}" if a != b else f"{a}"
        for name, i, path, s, e, excerpt, now in gone:
            state = f"narrowed to {', '.join(span(a, b) for a, b in now[:4])}" if now else "gone"
            print(f"{name}:{i} at {args.cites_since}: {path}:{span(s, e)} {state}, after \"{excerpt}\"")
        n_gone = sum(1 for g in gone if not g[-1])
        print(f"since {args.cites_since}: {n_gone} citations gone, {len(gone) - n_gone} narrowed "
              f"(no citation of the same file covers all of their lines now)")
    print()
    print(f"{'file':40} {'chars':>7} {'code':>5} {'rows':>5} {'figs':>4} {'pages':>6} {'code%':>6} {'cite/1k':>7}")
    total = 0.0
    for name, c, cl, tr, fg, pg, cr, cd in stats:
        total += pg
        print(f"{name:40} {c:7d} {cl:5d} {tr:5d} {fg:4d} {pg:6.2f} {cr:5.0f}% {cd:7.1f}")
    print(f"{'total':40} {'':7} {'':5} {'':5} {'':4} {total:6.2f}")
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
