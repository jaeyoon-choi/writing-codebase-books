# @TITLE@

<!-- 8단계에서 표지가 정해지면 이 줄을 ![표지](cover.svg)로 바꾼다. -->

이 디렉터리는 @REPO_NAME@의 구조를 코드 수준에서 설명하는 책의 원고다.

<!-- 독자와 목표를 설계 문서 1절에서 한두 문장으로 옮긴다. -->

- 저자: @AUTHOR@
- 기준 코드: @REPO_NAME@ 저장소 커밋 @COMMIT@
- 원고 형식: Markdown. 구성 요소 그림, 위치 그림, 구조 그림은 draw.io(`figures/*.drawio.svg`), 나머지 그림은 PlantUML
- 설계: [spec/book-design.md](spec/book-design.md)
- 재료: 코드 분석 연재(`../analysis/`)와 참고 자료(`../references/`). 원고의 사실은 모두 기준 커밋의 코드로 다시 확인했다

## 차례

<!-- book.toml의 [layout] order 순서로 서문, 부, 장, 부록, 찾아보기를 링크한다. -->

## 작업 자료

| 경로 | 내용 |
|---|---|
| `work/scenario.md`, `work/scenario.py` | 예제 시나리오의 숫자와 ID, 그 계산 스크립트 |
| `work/terms.md` | 고정 용어 목록 |
| `work/outline.md` | 확정 목차와 절 번호 |
| `work/*-brief.md` | 집필, 독자 검증, 검토, 문체 정리, 그림, 미확인 항목 정리, 강의 작성 지침 |
| `work/reviews/`, `work/approved/status.md` | 검토 보고와 승인 상태 |
| `work/notes/` | 장별 노트 (설계 교훈, 불변식, 설정 키, 테스트, 풀이) |
| `work/open-questions.md`, `work/oq-triage/` | 미확인 항목의 판정과 처리 기록, 판정 근거 |
| `figures/` | draw.io 그림과 그 생성 스크립트 (`figures/README.md`) |
| `tools/` | 인용 검사(`check_book.py`), 조판(`build_pdf.py`, `book.css`, `qa_pages.js`, `make_fonts.py`, `pdf_boxes.py`), 표지(`cover_template.py`, `build_cover.py`), 그림(`drawio_fig.py`, `seqdiag.py`, `embed_figures.py`, `measure_puml.py`) |
| `lecture/` | 강의 영상의 슬라이드 모듈과 빌드 스크립트 |

## 검사

```
python3 -I tools/check_book.py --xref preface.md part*.md ch*.md appendix-*.md index.md README.md
```

검사기는 기준 커밋에서 `git show`로 소스를 읽으므로, 저장소 작업 트리의 상태와 관계없이 동작한다.

## 조판

```
python3 -I tools/build_pdf.py            # 화면용 build/<파일>.pdf (표지 포함)
python3 -I tools/build_pdf.py --print    # 인쇄용 build/<파일>-print.pdf (표지 없음, 도련 3mm, 재단선, TrimBox)
python3 -I tools/build_cover.py          # 인쇄용 앞표지 build/cover-print.pdf
```

판형은 183 × 235mm이고, 한글 글꼴은 책에 쓰인 글자만 남긴 TrueType 사본으로 넣는다(PDF에 Type 3 글꼴이 없다). 책등과 뒤표지는 쪽수와 인쇄소의 종이에 따라 폭이 정해지므로 만들지 않는다.
