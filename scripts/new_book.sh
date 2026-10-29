#!/bin/bash
# Create a book directory for a codebase book.
#   bash new_book.sh <book dir> <source repo> <commit-ish> [title] [author]
# Copies the tools and the work templates, writes book.toml with the full
# commit hash, and lists what to do next. The source repository is only read.
set -euo pipefail
SKILL=$(cd "$(dirname "$0")/.." && pwd)
BOOK=$1; REPO=$(realpath "$2"); REV=$3
TITLE=${4:-"$(basename "$REPO") 구조"}; AUTHOR=${5:-"저자"}
COMMIT=$(git -C "$REPO" rev-parse --verify "$REV^{commit}")
[ -e "$BOOK/book.toml" ] && { echo "new_book.sh: $BOOK/book.toml exists" >&2; exit 1; }

mkdir -p "$BOOK"/{tools,work/notes,work/reviews,work/approved,work/evidence,figures/src,spec}
cp -r "$SKILL/tools/." "$BOOK/tools/"
mv "$BOOK/tools/lecture" "$BOOK/lecture"
mkdir -p "$BOOK/lecture/slides"
for t in writing-rules analysis-brief writer-brief reader-brief review-brief style-brief figure-brief oq-triage-brief lecture-brief; do
  cp "$SKILL/templates/$t.md" "$BOOK/work/$t.md"
done
cp "$SKILL/templates/figure-example.py" "$BOOK/work/figure-example.py"
cp "$SKILL/templates/figures-readme.md" "$BOOK/figures/README.md"
cp "$SKILL/templates/spec.md" "$BOOK/spec/book-design.md"
cp "$SKILL/templates/analysis-design.md" "$BOOK/spec/analysis-design.md"
mkdir -p "$BOOK/../analysis" "$BOOK/../references"
cp "$SKILL/templates/lecture-example.py" "$BOOK/lecture/example_part.py"
printf 'build/\n__pycache__/\nlecture/build/\n' > "$BOOK/.gitignore"
sed -e "s|^title = .*|title = \"$TITLE\"|" -e "s|^author = .*|author = \"$AUTHOR\"|" \
    -e "s|^repo = .*|repo = \"$REPO\"|" -e "s|^commit = .*|commit = \"$COMMIT\"|" \
    -e "s|^title_meta = .*|title_meta = [\"$(basename "$REPO")\", \"기준 커밋 ${COMMIT:0:7}\"]|" \
    "$SKILL/tools/book.toml.example" > "$BOOK/book.toml"
rm -f "$BOOK/tools/book.toml.example"
JAR=$(ls -d "$HOME"/.vscode/extensions/jebbs.plantuml-*/plantuml.jar 2>/dev/null | sort -V | tail -1 || true)
if [ -n "$JAR" ]; then sed -i "s|^plantuml_jar = .*|plantuml_jar = \"$JAR\"|" "$BOOK/book.toml"
else echo "warning: plantuml.jar not found; set [figures] plantuml_jar in book.toml" >&2; fi
sed -e "s|@TITLE@|$TITLE|" -e "s|@AUTHOR@|$AUTHOR|" -e "s|@COMMIT@|$COMMIT|" \
    -e "s|@REPO_NAME@|$(basename "$REPO")|g" "$SKILL/templates/book-readme.md" > "$BOOK/README.md"
mkdir -p "$BOOK/work/oq-triage"
echo "created $BOOK (source $REPO at ${COMMIT:0:12})"
echo "next: ask the user for existing analysis docs, then fill in spec/analysis-design.md (stage 1) before the book design"
echo "figures: work/figure-brief.md lists the .drawio.svg figures; start the component figure from work/figure-example.py"
