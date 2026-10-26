# 그림 원본

이 디렉터리의 `.drawio.svg` 파일은 책의 구성 요소 그림, 장 도입의 위치 그림, 배치와 자료 배치 같은 구조 그림이다. 파일 하나가 SVG 그림과 draw.io 모델을 함께 담으므로, GitHub와 Obsidian에서는 그림으로 보이고 draw.io(데스크톱 앱이나 diagrams.net)에서는 열어서 고칠 수 있다. 그 밖의 그림은 원고 안의 PlantUML 블록이다. 어떤 그림을 어떤 형식으로 그리는지는 `work/figure-brief.md` 1절에 있다.

| 경로 | 내용 |
|---|---|
| `fig-<장>-<번호>-<이름>.drawio.svg` | 원고가 이미지로 넣는 그림 |
| `src/components.py` | 구성 요소 그림과 위치 그림 N.1. 장별 강조는 이 파일의 `CHAPTERS` 표에 있다 |
| `src/fig_<장>_<번호>.py` | 그 밖의 draw.io 그림을 처음 만든 스크립트. `tools/drawio_fig.py`를 쓰고, 시퀀스 그림은 `tools/seqdiag.py`도 쓴다 |

스크립트로 다시 만들려면 책 디렉터리에서 `python3 -I figures/src/<스크립트>.py`를 실행한다. draw.io에서 고친 그림은 그 파일이 원본이 되므로, 고친 뒤에는 그 그림의 스크립트를 다시 실행하지 않고 이 표에 그 사실을 적는다. 미리보기 PNG는 `bash tools/preview_svg.sh <그림> <출력.png>`로 만든다(헤드리스 Chrome을 쓴다).
