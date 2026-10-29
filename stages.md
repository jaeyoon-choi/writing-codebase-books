# 단계별 절차

경로의 기준은 책 디렉터리(`~/Documents/Claude/<저장소>/book`)다. `<스킬>`은 `~/.claude/skills/writing-codebase-books`다.

## 필요한 것

| 도구 | 쓰는 곳 | 없을 때 |
|---|---|---|
| Python 3.11 이상, `markdown`, `pygments`, `Pillow`, `fontTools`, `websocket-client` | 모든 도구 | 사용자에게 설치를 묻는다 |
| `google-chrome` | PDF 조판, 그림 미리보기, 강의 슬라이드 | 사용자에게 묻는다 |
| poppler (`pdftotext`, `pdffonts`, `pdfinfo`, `pdftoppm`) | 쪽 확인 | 사용자에게 묻는다 |
| Java와 `plantuml.jar` | PlantUML 그림 | VS Code PlantUML 확장의 jar를 `book.toml`에 적는다 |
| Noto CJK 글꼴 | 본문 | 시스템 글꼴을 쓴다 |
| `edge-tts`, `imageio-ffmpeg` (venv) | 강의 영상(선택) | 설치 전에 사용자의 허락을 받는다 |

## 0. 준비

`bash <스킬>/scripts/new_book.sh <책 디렉터리> <저장소> <커밋> "<제목>" "<저자>"`로 책 디렉터리를 만든다. 스크립트는 `tools/`, `lecture/`, `work/`의 지침들, `spec/book-design.md`와 `spec/analysis-design.md`(틀), 전체 해시를 적은 `book.toml`, 책 `README.md`, 책 디렉터리 옆의 `analysis/`와 `references/`를 만든다. 저장소가 git이 아니거나 작업 트리가 기준 커밋과 달라도 도구는 `git show`로 읽으므로 상관없다.

## 1. 사전 분석

책은 코드 분석 연재 위에서 쓴다. 분석 연재는 사용자가 시스템을 처음 깊게 읽는 학습 문서이고, 책의 장 구조, 장마다 가져올 내용, 집필자가 다시 확인할 사실의 목록이 여기서 나온다. 분석 문서와 참고 자료는 책 디렉터리 옆(`~/Documents/Claude/<저장소>/analysis/`, `references/`)에 둔다.

1. 기존 자료 확인: 사용자에게 이 저장소의 분석 문서, 설계 노트, 조사 자료가 이미 있는지 묻는다. 있으면 `spec/analysis-design.md` 6절에 등록하고, `python3 -I tools/check_book.py <문서>`로 앵커와 인용을 검사해 틀린 곳을 비고에 적는다. 이 경우 아래 2~4번은 빠진 하위 시스템에만 한다.
2. 분석 설계: 저장소를 조사하고(`git -C <저장소> ls-tree -r --name-only <커밋>`, 문서, 형식 명세, 테스트) `spec/analysis-design.md`를 채운다. 편은 하위 시스템마다 하나이고, 편마다 답할 질문과 선행 편을 적는다. 사용자에게 보이고 승인을 받는다.
3. 분석 연재: 주 세션이 `work/analysis-brief.md`대로 0편을 얕게 먼저 쓰고, 의존 순서대로 1편부터 쓴 뒤, 마지막에 0편을 갱신한다. 코드 읽기를 서브에이전트에 나눠 맡기지 않는다. 편마다 `check_book.py` 0건을 확인하고 사용자에게 보인다. 사용자의 피드백(예: "큰 그림을 먼저")은 다음 편과 `work/analysis-brief.md`에 반영한다. 연재는 여러 세션에 걸치므로 진행 상태를 설계 문서 6절에 적는다.
4. 참고 자료: `spec/analysis-design.md` 5절의 주제마다 `../references/주제.md`를 쓴다(`work/analysis-brief.md` 5절). 이 자료가 책의 "다른 시스템의 선택"과 참고 문헌의 출처가 된다.

사용자가 응답할 수 없는 실행에서는 분석 설계 0절에 질문과 가정한 답을 적고, 편마다 진행 상태에 "확인 대기"로 적는다.

## 2. 설계

1. 분석 연재와 그동안 받은 사용자의 피드백을 다시 읽는다. 장 구조는 분석의 편 구조에서 출발하되, 독자가 따라갈 순서(문제, 전체 구조, 토대, 제어 경로, 데이터 경로, 장애와 운영, 평가)로 다시 짠다.
2. superpowers:brainstorming 절차로 독자, 목표, 범위, 부와 장을 사용자와 정한다. 질문은 하나씩 한다.
3. `spec/book-design.md`의 틀을 채운다. 장별 설계(8절)에는 장마다 목표 쪽수, 핵심 질문, 절 목록, 다룰 코드 경로, 예제 시나리오의 장면, 가져올 것(분석 편과 절, 참고 자료)을 적는다.
4. 사용자에게 설계 문서를 보이고 승인을 받는다. 바꿀 것이 생기면 설계 문서를 먼저 고친다.

## 3. 기준 자료

- `work/scenario.py`: 예제 시나리오(노드, 디스크, 데이터, 요청, 사건 2~3개)의 숫자와 ID를 코드의 규칙으로 계산하는 스크립트. 결과를 `work/scenario.md`에 표로 적는다.
- `work/terms.md`: 고정 용어 표(용어, 영어 또는 식별자, 뜻, 정의한 장).
- `work/outline.md`: 확정 절 번호와 장별 목표 쪽수.
- `book.toml`의 `[layout] order`: 읽는 순서(front, part, ch, app). 아직 쓰지 않은 파일은 화면용 빌드와 `measure_puml.py`가 경고하고 건너뛰고, 인쇄용 빌드(`--print`)는 멈춘다.
- 템플릿 견본 한 쪽: `work/template-sample.md`에 장의 일부를 옮기고 `python3 -I tools/build_sample.py`로 `build/template-sample.pdf`를 만들어 사용자에게 판형을 보인다.

## 4. 집필

1. 구조 장을 먼저 쓴다. 이 장이 구성 요소 그림(위치 그림의 바탕)과 예제 시나리오의 서술을 정한다. 구조 장의 코드 개요는 소스 트리와 읽는 법(설계 문서 5절 7번)을 담는다. 코드를 읽으려는 독자가 처음 찾는 내용이므로 부록에만 두지 않는다.
2. 구조 장이 승인되면 주 세션이 `work/figure-example.py`를 `figures/src/components.py`로 복사해 이 책의 구성 요소로 바꾸고, 구조 장의 구성 요소 그림과 구조 장을 뺀 모든 장의 위치 그림 N.1을 `.drawio.svg`로 만든다(`work/figure-brief.md` 2~3절). `BASE`의 번호는 구조 장의 그림 번호에 맞추고, 장별 강조(`CHAPTERS`)는 설계 문서 8절의 다룰 코드 경로로 정한다. 구조 장의 구성 요소 그림 PlantUML 블록은 `python3 -I tools/embed_figures.py`로 이미지 줄로 바꾼다.
3. 서브에이전트가 결과 파일을 쓰지 못할 수 있다(하네스가 보고서 파일 쓰기를 거부한 사례가 있다). 그래서 검토, 독자 검증, 판정을 맡긴 에이전트에게는 지정한 파일에 쓰되, 쓰기가 막히면 보고 전체를 응답 본문으로 돌려주라고 지시한다. 주 세션은 받은 본문을 지정한 경로에 저장한 뒤 다음 단계로 간다.
4. 나머지 장은 에이전트 하나에 장 하나를 맡겨 병렬로 쓴다. 프롬프트에는 `work/writer-brief.md`를 읽고 따르라는 지시, 맡은 장의 파일 이름, 승인된 구조 장의 경로만 준다.
5. 장마다 다음을 차례로 거친다.
   - 집필 에이전트가 `python3 -I tools/check_book.py chNN-*.md`를 0건까지 고친다.
   - 독자 검증: 새 에이전트가 `work/reader-brief.md`대로 읽고, 막힌 곳을 `work/reviews/chNN-reader.md`에 적는다. 집필 에이전트(또는 새 에이전트)가 고친다.
   - 검토: 새 에이전트가 `work/review-brief.md`대로 검토해 `work/reviews/chNN-rK.md`에 쓴다. 차단과 주요 발견을 고치고 다시 검토한다. 마지막 줄이 `Reviewed-by:`이면 `work/approved/status.md`에 장과 검토 파일을 적는다.
6. 노트(`work/notes/chNN.md`)의 공유 파일 수정 제안은 주 세션이 모아 `scenario.md`, `terms.md`, `outline.md`, 위치 그림의 `CHAPTERS` 표에 반영하고, 영향을 받는 장에 알린다(`work/pending-edits.md`). 노트의 draw.io 대상 그림 목록은 7단계에서 쓴다.
7. 책 디렉터리가 git 저장소 안에 있으면 주 세션이 승인된 장마다 책 경로로 한정해 커밋한다. 푸시는 사용자가 요청할 때 한다.
8. 미확인 항목은 노트에서 `work/open-questions.md`로 모은다. 판정은 6단계에서 한다.

## 5. 마무리 원고

첫 장(문제 정의), 마지막 장(설계 결정의 대가와 교훈: 노트의 설계 교훈을 모은다), 부 도입, 부록(소스 트리와 장 대응, 설정 키 색인, 용어집, 문제 풀이, `work/evidence/`를 모은 장별 근거 위치), 찾아보기, 서문을 쓴다. 노트 파일들이 이 원고들의 재료다. 각각 검토 승인을 받는다. 책 디렉터리의 `README.md`(소개, 차례, 작업 자료, 검사, 조판)의 소개와 차례를 채운다.

## 6. 전권 정리

1. 미확인 항목 정리: `work/open-questions.md`를 장 묶음 서너 개로 나눠 에이전트마다 `work/oq-triage-brief.md`를 주고 항목을 판정하게 한다. 결과는 `work/oq-triage/`에 쌓인다. 주 세션(또는 반영 에이전트)이 바꿀 문장과 "다른 파일의 변경"을 원고에 반영하고, `open-questions.md`의 항목마다 판정과 처리 결과를 적어 닫는다. 실측 부록에서 확인할 항목은 그 부록의 항목으로 옮긴다.
2. 변경분 검토: 1번에서 바뀐 부분만 새 검토자에게 `work/review-brief.md`로 검토하게 하고(`git diff`를 함께 준다), 결과를 `work/reviews/delta-*.md`에 쓴다. `Reviewed-by:`를 받을 때까지 고친다.
3. `python3 -I tools/check_book.py --xref preface.md part*.md ch*.md appendix-*.md index.md README.md`가 0건이어야 한다. `--xref`는 `N.M절` 참조가 실제 절을 가리키는지 본다.
4. 분량 점검: 장 묶음마다 새 검토자에게 원고를 읽기만 하게 하고, 독자에게 필요 없는 세부(다른 장의 반복, 리스팅을 줄마다 다시 말하는 해설, 설계와 관계없는 보일러플레이트, 기본 설정에서 쓰지 않는 경로, 본문 안의 전수 나열)의 후보를 위치, 이유, 줄어드는 쪽, 확신, 고쳐야 할 참조와 함께 내게 한다. 결과는 `work/reviews/trim-candidates.md`에 모으고, 사용자가 반영 범위를 고른다. 반영한 뒤 2번처럼 변경분을 검토한다. 3FS 책에서는 장마다 목표보다 8~12쪽이 많았고 후보가 약 90쪽이었다.
5. 문체 정리: 장을 나눠 에이전트에게 `work/style-brief.md`를 주고, 사실과 구조는 그대로 둔 채 AI 문장 틀만 고치게 한다. 다른 에이전트가 고친 결과를 검토한다.

## 7. 그림

어떤 그림이 draw.io 그림(`.drawio.svg`)이고 어떤 그림이 PlantUML 블록인지는 `work/figure-brief.md` 1절의 표가 정한다. 구성 요소 그림과 위치 그림은 4단계에서 이미 만들었다.

1. 대상 목록: 노트의 draw.io 대상 그림과, 원고의 PlantUML 블록 중 1절의 표에서 draw.io 대상인 그림(배치, 자료 배치, 설계 비교, 여러 장이 가리키는 상태 전이)을 `work/figures.md`에 모은다. 사용자에게 목록을 보이고 더하거나 뺄 그림을 묻는다.
2. 다시 그리기: 에이전트 하나에 그림 서너 개를 맡겨 병렬로 그린다. 프롬프트에는 `work/figure-brief.md`를 읽고 따르라는 지시와 그림 번호만 준다. 에이전트는 `figures/src/fig_N_M.py`와 `figures/fig-N-M-이름.drawio.svg`를 만들고 미리보기로 확인한다.
3. 원고에 넣기: `python3 -I tools/embed_figures.py`가 같은 번호의 PlantUML 블록을 이미지 줄로 바꾼다. 그림의 표시 방식(굵은 테두리, 강조색)을 설명하는 본문 문장과 서문을 새 그림에 맞춘다.
4. 남은 PlantUML: 조판할 때 `build_pdf.py`가 인쇄용 설정(12px 글자, 좁은 간격)을 덧붙인다. `python3 -I tools/measure_puml.py`가 7pt 미만인 그림을 보고한다. 보고된 그림은 에이전트에게 `work/figure-brief.md` 4절대로 배치만 고치게 한다. 배치를 바꿔도 7pt 미만인 시퀀스 그림은 `tools/seqdiag.py`로 다시 그리고 3번을 반복한다.
5. 그림 검토: 새 에이전트가 `work/figure-brief.md` 5절대로 그림을 넣은 커밋을 검토한다. 차단과 주요 발견을 고치고 `Reviewed-by:`를 받는다.
6. `figures/README.md`의 표를 실제 파일에 맞춘다.

인쇄 규칙: 680px 캔버스가 본문 폭 143mm에 맞고 글자는 12px 이상이어야 7pt 이상으로 인쇄된다. 높이는 178mm 이하다. `drawio_fig.py`는 이 규칙을 어기면 경고한다. `bash tools/preview_svg.sh <svg> <png>`로 미리 본다.

## 8. 조판

- `python3 -I tools/cover_template.py`로 표지(`cover.svg`, `cover-print.svg`)를 만든다. 그림이 있으면 `figures/cover-art.svg`에 둔다. 표지 그림은 시안을 PNG로 만들어 사용자에게 보이고 고르게 한다. 3FS 책에서는 여러 시안 중 프로젝트를 상징하는 동물(고래)을 선 해칭 판화풍으로 그린 시안을 사용자가 골랐다. 표지에는 저자 이름을 넣는다. 표지가 정해지면 `README.md` 맨 위의 표지 줄을 채운다.
- `python3 -I tools/build_pdf.py`: 화면용 `build/<file>.pdf`. 한글 글꼴을 TrueType으로 바꿔 넣고(Type 3 글꼴 없음), Paged.js로 배치한 뒤 쪽마다 검사하고(`tools/qa_pages.js`), 쪽 끝에 홀로 남은 제목, 한 줄만 넘어간 문단, 큰 그림이나 리스팅 때문에 빈 쪽을 다음 배치에서 고친다. 남은 항목은 `build/<file>-qa.txt`에 있다.
- `python3 -I tools/build_pdf.py --print`: 인쇄소용 내지(표지 없음, 도련 3mm, 재단선, TrimBox). `python3 -I tools/build_cover.py`: 인쇄용 앞표지.
- 확인: `pdffonts`에 Type 3이 없는지, QA 파일에 넘침이나 사라진 내용(`lost`)이 없는지, 전 쪽을 접촉 인쇄(contact sheet)로 넘겨 보는지(에이전트에게 나눠 맡긴다).

## 9. 선택 단계

### 실측 부록

계산한 숫자를 실제 프로세스에서 확인한다. 사용자에게 실행 환경(VM, 테스트 클러스터)을 확인하고 시작한다. 항목마다 책의 계산 규칙과 기대값을 먼저 적고, 측정 방법(로그, 조회, 추적)과 그 방법으로 알 수 없는 것을 적은 뒤 측정한다. 부록은 `work/writing-rules.md`의 분석 보고서 규칙(요약, 원리 먼저, 예상값과 측정값 대조, 확인하지 못한 것과 다음 단계)을 따른다. 측정과 맞지 않는 본문은 고치고 부록에서 대조한다.

### 강의 영상

- `lecture/slides/`에 모듈 하나가 강의 하나다. 책 전체를 요약하는 5분 강의(`overview.py`)를 먼저 만들어 사용자에게 보이고, 형식이 정해지면 부별 강의로 넓힌다. 강의마다 에이전트 하나에 `work/lecture-brief.md`와 `lecture/example_part.py`를 주고 `lecture/slides/overview.py` 또는 `partN.py`를 쓰게 한다(`work/lecture-brief.md` 2절). 에이전트는 `python3 -I lecture/build_lecture.py --lecture <모듈 이름> --preview`로 그림만 만들어 확인한다.
- 영상은 `python3 lecture/build_lecture.py --all --tts <venv>/bin/edge-tts --ffmpeg <ffmpeg>`로 만든다. MP4(H.264, AAC, 한국어 자막 트랙), 자막(SRT), 대본(Markdown)이 `lecture/videos/`와 `lecture/scripts/`에 생긴다. edge-tts와 imageio-ffmpeg는 사용자의 허락을 받고 venv에 설치한다.
