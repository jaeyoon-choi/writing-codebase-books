#!/usr/bin/env python3
"""Merge work/evidence/chNN.md into the evidence appendix.

Each evidence file starts with a title line and an intro paragraph, then "## X.N ..." sections of
tables (X is the appendix letter). Only the sections are copied.
Run: python3 -I tools/build_evidence.py appendix-f-evidence.md
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bookconf import BOOK, source  # noqa: E402

out_name = sys.argv[1] if len(sys.argv) > 1 else "appendix-f-evidence.md"
commit = source()["commit"][:12]
sections, letter = [], None
for f in sorted((BOOK / "work" / "evidence").glob("ch[0-9][0-9].md")):
    lines = f.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(r"## [A-Z]\.\d", l))
    letter = letter or lines[start][3]
    body = lines[start:]
    while body and not body[-1].strip():
        body.pop()
    sections += body + [""]

out = [f"# 부록 {letter} 근거 위치", "",
       f"이 부록은 각 장의 본문이 함수와 단계로만 적은 서술을 받치는 소스 위치를 장별 표로 모은다. "
       f"본문의 \"부록 {letter}.N\"은 이 부록의 N장 절을 가리킨다. 위치는 기준 커밋 `{commit}`의 `경로:줄`이고, "
       f"`git -C <저장소> show {commit}:<경로>`로 열면 같은 줄이 나온다. 다른 저장소의 위치는 그 장의 참고 문헌에 적은 "
       f"저장소와 커밋을 따른다. 표의 절 열은 그 위치가 받치는 본문의 절이다.", ""] + sections
(BOOK / out_name).write_text("\n".join(out), encoding="utf-8")
print(f"{out_name}: {len(out)} lines")
