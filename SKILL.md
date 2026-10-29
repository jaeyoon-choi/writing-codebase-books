---
name: writing-codebase-books
description: Use when asked to write a book, book-length guide or chapter series that explains a source code repository's internals or architecture (코드 해설서, 구조 책, 책 만들기, 출판 품질 원고), or to produce such a book's figures, print-ready PDF, cover, measurement appendix or lecture videos.
---

# 코드베이스 해설서 만들기

## 개요

코드 해설서는 모든 주장이 고정된 커밋 하나에 묶인 긴 문서다. 책은 코드에서 바로 쓰지 않고, 먼저 쓴 코드 분석 연재 위에서 쓴다. 3FS 책은 분석 연재 12편(290KB)과 참고 자료 조사를 재료로 삼았고, 책 설계의 장 구조와 장마다 "가져올 것"이 그 연재에서 나왔다. 작업은 관문이 있는 단계로 진행하고, 검증된 도구(`tools/`)를 그대로 쓴다. 검사기나 조판 도구를 새로 만들지 않는다. 각 단계의 명령과 산출물은 `stages.md`에 있다.

## 단계와 관문

| 단계 | 산출물 | 다음 단계로 가는 조건 |
|---|---|---|
| 0. 준비 | `bash <스킬>/scripts/new_book.sh ~/Documents/Claude/<저장소>/book <저장소> <커밋> "<제목>" "<저자>"` | `book.toml`에 전체 해시가 있음 |
| 1. 사전 분석 | `spec/analysis-design.md`, `../analysis/NN-이름.md` (0편 개요와 하위 시스템마다 한 편), `../references/*.md` | **사용자가 분석 설계를 승인함.** 편마다 `check_book.py` 0건이고 사용자가 읽고 확인함. 기존 분석 자료가 있으면 등록하고 빠진 편만 쓴다 |
| 2. 설계 | `spec/book-design.md` (틀이 들어 있음) | **사용자가 설계를 승인함. 승인 전에는 원고를 쓰지 않는다.** 사용자가 응답할 수 없는 실행에서는 설계 문서 0절에 질문과 가정한 답을 적고, 그 뒤에 쓴 원고를 `work/approved/status.md`에 "승인 대기"로 적는다 |
| 3. 기준 자료 | `work/scenario.py`·`scenario.md`, `work/terms.md`, `work/outline.md`, `book.toml`의 장 순서 | 세 파일이 있음 |
| 4. 집필 | 구조 장을 먼저 쓰고, 승인되면 구성 요소 그림과 나머지 장의 위치 그림을 `.drawio.svg`로 만든다. 그다음 장마다 에이전트 하나: 초고 → `check_book.py` 0건 → 독자 검증 → 검토 | 장마다 `Reviewed-by:` 줄, `work/approved/status.md`에 기록 |
| 5. 마무리 원고 | 첫 장, 마지막 장, 부 도입, 부록, 찾아보기, 서문, 책 `README.md` | 검토 승인 |
| 6. 전권 정리 | 미확인 항목 판정(`work/oq-triage-brief.md`)과 변경분 검토, `check_book.py --xref <전체>`, 문체 정리(`work/style-brief.md`) | **`open-questions.md`의 모든 항목이 닫힘**, 변경분 `Reviewed-by:`, 전권 검사 0건 |
| 7. 그림 | 아래 그림 형식 표의 `.drawio.svg` 대상을 모두 다시 그림(`work/figure-brief.md`), 남은 PlantUML은 인쇄 7pt 이상(`measure_puml.py`) | 라이브러리 경고 0, 측정 통과, 그림 검토 `Reviewed-by:` |
| 8. 조판 | `build_pdf.py`, `build_pdf.py --print`, `cover_template.py`, `build_cover.py` | Type 3 글꼴 0개, 쪽 검사 통과, 사용자가 표지 시안을 고름 |
| 9. 선택 | 실측 부록, 5분 전체 요약 강의와 부별 강의 영상 | 사용자가 요청할 때 |

## 바꾸지 않는 규칙

- 책 설계 전에 사전 분석 연재를 쓴다. 분석은 주 세션이 코드를 직접 읽고 쓴다(`work/analysis-brief.md`). 집필자는 분석 문서를 재료로 쓰되 모든 사실을 코드로 다시 확인한다.
- 코드는 `git -C <저장소> show <커밋>:<경로>`로만 읽는다. 저장소를 고치거나 체크아웃하거나 빌드하지 않는다.
- 모든 장은 설계 문서 4절의 틀을 따른다: 장 도입(위치 그림, 핵심 질문 상자), 전체 그림(역할 이름의 그림과 단계-절 대응 표), 개념 절, 코드 개요, 코드 절, 다른 시스템의 선택, 정리, 생각해 볼 문제, 참고 문헌. 설계 교훈과 불변식은 번호를 붙인다.
- 코드로 확인하지 못한 사실은 원고에 넣지 않는다. "추론이다", "추정한다"로 남기지 않고 `work/open-questions.md`로 보낸다.
- 숫자는 `scenario.md`, 코드 규칙으로 계산한 값, 출처가 있는 인용 중 하나이고, 가정한 값에는 "가정"이라고 적는다.
- 원고, 분석 연재, 강의 대본은 `work/writing-rules.md`의 문장 규칙을 따른다. 이 파일은 스킬의 `templates/writing-rules.md`이고, 사용자의 전역 지침(`~/.claude/CLAUDE.md`)에서 문서에 관한 절을 옮긴 것이다. 전역 지침의 그 절이 바뀌면 이 템플릿도 함께 고친다.

## 그림 형식

중요한 그림은 draw.io 그림(`.drawio.svg`)으로 그린다. `tools/drawio_fig.py`가 SVG와 draw.io 모델을 한 파일에 쓰므로 draw.io를 설치하지 않아도 된다. Mermaid는 쓰지 않는다.

| 그림 | 형식 |
|---|---|
| 구성 요소 그림, 위치 그림 N.1 | `.drawio.svg`: `figures/src/components.py` 하나에 장별 강조 표 (`work/figure-example.py`에서 시작) |
| 장 첫머리의 전체 그림 N.2, 구조 장의 디렉터리 계층 그림 | `.drawio.svg`: 집필 때 그림마다 `figures/src/fig_N_M.py` |
| 배치, 자료 배치, 설계 비교, 여러 장이 가리키는 상태 전이 | `.drawio.svg`: 그림마다 `figures/src/fig_N_M.py` |
| 참여자가 많아 7pt를 지킬 수 없는 시퀀스 | `.drawio.svg`: `tools/seqdiag.py` |
| 그 밖의 시퀀스, 클래스 관계, 절차, 한 장 안의 상태 | 원고 안의 PlantUML 블록 |

## 흔한 실수

| 실수 | 대신 할 일 |
|---|---|
| 저장소를 훑어보고 바로 책 설계로 간다 | 사전 분석 연재를 먼저 쓰고 사용자의 확인을 받는다. 장 구조는 분석 연재와 그 피드백에서 나온다 |
| 분석의 코드 읽기를 에이전트들에게 나눠 맡긴다 | 주 세션이 의존 순서대로 직접 읽는다. 분석은 직접 읽은 사람만 쓸 수 있다 |
| 깊은 장부터 쓴다 | 구조 장을 먼저 쓴다. 그 장이 위치 그림의 바탕과 예제 시나리오의 서술을 정한다 |
| 사용자 답을 가정하고 설계를 넘긴다 | 설계 문서를 보이고 승인을 받는다 |
| pandoc이나 LaTeX로 PDF를 계획한다 | `tools/build_pdf.py`를 쓴다 (헤드리스 Chrome과 Paged.js, 설치 불필요) |
| "PlantUML이 없다"고 그림을 미룬다 | `book.toml`의 `[figures] plantuml_jar` 경로(VS Code 확장의 jar)를 쓴다 |
| 모든 그림을 PlantUML로 둔다 | 그림 형식 표의 `.drawio.svg` 대상은 draw.io 그림으로 그린다 |
| draw.io가 없어서 draw.io 그림을 미룬다 | `tools/drawio_fig.py`로 만든다 (설치 불필요) |
| 위치 그림을 장마다 따로 그린다 | 구성 요소 그림 하나의 배치에 장별 강조만 바꿔 만든다 |
| 미확인 항목을 남긴 채 조판한다 | 6단계에서 항목마다 확인, 원고에 주장 없음, 원고 수정 필요로 판정해 모두 닫는다 |
| 인용 검사기나 문체 검사기를 새로 만든다 | `tools/check_book.py`를 쓴다 |
| 장마다 구성이 다르다 | 설계 문서 4절의 틀과 `work/writer-brief.md`를 집필 에이전트에게 준다 |
| 장이 클래스와 함수 설명으로 바로 들어가 전체 그림이 없다 | 장 첫머리에 역할 이름의 draw.io 그림과 단계-절 대응 표를 두고, 개념 절을 그 그림 안의 자리에서 시작한다 |
| 개념 절 문단마다 `경로:줄`이 대여섯 개씩 붙는다 | 한 문단 3곳, 1,000자당 2~3곳으로 줄이고 나머지는 코드 절의 위치 표로 옮긴다(지우지 않는다). `check_book.py`가 경고하고 `cite/1k`를 보인다 |
| 예제 사건을 "사건 1, 2, 3"으로 부른다 | 무엇을 하는지 드러나는 이름을 붙인다("샘플 읽기", "storage3 장애") |
| 소스 트리 설명을 부록에만 둔다 | 구조 장에 디렉터리 계층 그림, 프로세스와 `main()` 표, 빌드와 외부 라이브러리, 읽는 순서를 둔다 |
| 다시 쓰는 에이전트가 고친 인용 줄 번호를 그대로 받는다 | 바뀐 인용은 주 세션이나 검토자가 `git show`로 하나씩 확인한다. 맞던 인용이 틀리게 바뀐 사례가 있다 |
