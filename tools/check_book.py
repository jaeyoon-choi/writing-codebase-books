#!/usr/bin/env python3
"""Check book chapters against the pinned commit of the source repository and the writing rules.

Checks, per file:
  - every `path:line` citation names a file at BASE and a line inside it
  - every listing whose first line is `// path:line` (or `# path:line`)
    starts at that line and then follows the source in order
  - no em dash, no Mermaid, no hard-wrapped paragraphs
  - headings are noun phrases (no sentence or question endings)      [lang = "ko"]
  - paragraph sentences end with a predicate (heuristic: `다.` and friends)  [lang = "ko"]
With several files, also checks that every `N.M절` reference names a
numbered heading somewhere in the set.

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
FENCE_OPEN = re.compile(r"^```(\w[\w+-]*)?\s*$")
ORIGIN = re.compile(r"^\s*(?://|#|--)\s*(" + PATH_RE + r"):(\d+)\s*$")
HANGUL = re.compile(r"[가-힣]")
ELISION = re.compile(r"^\s*(//\s*\.\.\.|#\s*\.\.\.|\.\.\.|/\*\s*\.\.\.\s*\*/)\s*$")
XREF = re.compile(r"(\d{1,2})\.(\d{1,2})절")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
FIG_ALT = re.compile(r"^그림 \d+\.\d+ \S")
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


def check_file(doc: Path, problems, headings, xrefs, stats):
    text = doc.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_fence = False
    fence_lang = None
    block = []
    block_start = 0
    prose_chars = code_lines = table_rows = figures = 0
    prev_para = False
    last_full_paths = []

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

        for path, start, end in ANCHOR.findall(raw):
            check_range(path, start, end, where, problems)
            last_full_paths.append(path)
        for name, start, end in SHORT.findall(raw):
            cands = [p for p in last_full_paths if p.rsplit("/", 1)[-1] == name]
            if not cands:
                cands = basename_index().get(name, [])
            if len(cands) >= 1:
                check_range(cands[-1] if cands else name, start, end, where, problems)
            else:
                problems.append(f"{where}: short citation with unknown file: {name}:{start}")
        for a, b in XREF.findall(raw):
            xrefs.append((int(a), int(b), where))

        hm = HEADING.match(raw)
        if hm:
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
            prev_para = False
            continue
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
    stats.append((doc.name, prose_chars, code_lines, table_rows, figures, pages,
                  (code_pages / pages * 100) if pages else 0))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--xref", action="store_true", help="check N.M절 references across the given files")
    args = ap.parse_args(argv[1:])
    problems, headings, xrefs, stats = [], set(), [], []
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            problems.append(f"no such file: {f}")
            continue
        check_file(p, problems, headings, xrefs, stats)
    if args.xref:
        for a, b, where in xrefs:
            if (a, b) not in headings:
                problems.append(f"{where}: reference to {a}.{b}절 but no such numbered heading")
    for p in problems:
        print(p)
    print()
    print(f"{'file':40} {'chars':>7} {'code':>5} {'rows':>5} {'figs':>4} {'pages':>6} {'code%':>6}")
    total = 0.0
    for name, c, cl, tr, fg, pg, cr in stats:
        total += pg
        print(f"{name:40} {c:7d} {cl:5d} {tr:5d} {fg:4d} {pg:6.1f} {cr:5.0f}%")
    print(f"{'total':40} {'':7} {'':5} {'':5} {'':4} {total:6.1f}")
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
