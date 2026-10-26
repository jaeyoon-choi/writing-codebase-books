#!/bin/sh
# usage: preview_svg.sh in.svg out.png  (renders at 2x)
# The first width and height attributes are the canvas size, with or without a "px" suffix.
w=$(grep -o 'width="[0-9.]*\(px\)\?"' "$1" | head -1 | grep -o '[0-9]*' | head -1)
h=$(grep -o 'height="[0-9.]*\(px\)\?"' "$1" | head -1 | grep -o '[0-9]*' | head -1)
d=$(mktemp -d)
printf '<html><body style="margin:0"><img src="file://%s" width="%s" height="%s"></body></html>' "$(realpath "$1")" "$w" "$h" > "$d/p.html"
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars --force-device-scale-factor=2 --window-size="$w,$h" --screenshot="$2" "file://$d/p.html" >/dev/null 2>&1
rm -rf "$d"
