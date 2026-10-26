# writing-codebase-books

코드 저장소의 내부 구조를 코드 수준에서 해설하는 책을 만드는 Claude Code 스킬이다. 사전 코드 분석부터 책 설계, 장 집필과 검토, draw.io 그림, 인쇄용 PDF와 표지, 선택 단계인 실측 부록과 강의 영상까지를 관문이 있는 단계로 진행한다. DeepSeek 3FS를 해설한 667쪽 책 『3FS 구조』를 만든 과정과 도구를 일반화했다.

## 설치

```
git clone https://github.com/jaeyoon-choi/writing-codebase-books.git ~/.claude/skills/writing-codebase-books
```

Claude Code를 다시 시작하면 "이 저장소 구조를 설명하는 책을 쓰자"처럼 요청할 때 스킬이 쓰인다. 갱신은 같은 디렉터리에서 `git pull`로 한다.

## 필요한 것

| 도구 | 쓰는 곳 |
|---|---|
| Python 3.11 이상, `markdown`, `pygments`, `Pillow`, `fontTools`, `websocket-client` | 모든 도구 |
| `google-chrome` | PDF 조판(헤드리스 Chrome과 Paged.js), 그림 미리보기, 강의 슬라이드 |
| poppler (`pdftotext`, `pdffonts`, `pdfinfo`, `pdftoppm`) | 쪽 확인 |
| Java와 `plantuml.jar` | PlantUML 그림. VS Code PlantUML 확장(jebbs)이 있으면 `new_book.sh`가 그 jar를 찾아 쓴다 |
| Noto CJK 글꼴 | 한글 본문 |
| `edge-tts`, `imageio-ffmpeg` | 강의 영상(선택) |

draw.io 그림은 `tools/drawio_fig.py`가 SVG와 draw.io 모델을 한 파일(`.drawio.svg`)에 쓰므로 draw.io를 설치하지 않아도 된다.

## 구성

| 경로 | 내용 |
|---|---|
| `SKILL.md` | 단계와 관문, 바꾸지 않는 규칙, 그림 형식, 흔한 실수 |
| `stages.md` | 단계별 절차와 명령 |
| `templates/` | 분석 설계와 분석 지침, 책 설계 틀, 집필, 독자 검증, 검토, 문체 정리, 그림, 미확인 항목 정리, 강의 지침, 문장 규칙(`writing-rules.md`) |
| `tools/` | 인용 검사기(`check_book.py`), 조판(`build_pdf.py`), 표지, 그림, 강의 빌드 |
| `scripts/new_book.sh` | 새 책 디렉터리를 만들고 도구와 지침을 복사한다 |

## 알아 둘 것

- 기본 문서 위치는 `~/Documents/Claude/<저장소>/book`(책), `analysis/`(분석 연재), `references/`(참고 자료)이다. `new_book.sh`에 다른 경로를 주면 그 경로를 쓴다.
- 문장 규칙(`templates/writing-rules.md`)은 한국어 기술 문서를 위한 저자의 규칙이다. 엠대시 금지, 명사구 제목, 서술어로 끝나는 문장, AI 문장 틀 금지 등을 담는다. 팀의 규칙이 다르면 이 파일을 고친다.
- 대상 저장소는 읽기만 한다. 모든 인용은 `book.toml`에 고정한 기준 커밋을 `git show`로 읽어 검사한다.
- `tools/vendor/pagedjs/`는 Paged.js 0.4.3이며 MIT 라이선스를 따른다(`LICENSE.md`).

## 라이선스

MIT 라이선스(`LICENSE`)를 따른다. `tools/vendor/pagedjs/`는 Paged.js의 MIT 라이선스(`tools/vendor/pagedjs/LICENSE.md`)를 따른다.
